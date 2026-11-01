import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.package_artifacts import sanitized_environment, validate_artifacts
from scripts.publish_forgejo import preflight
from scripts.release_version import parse_release_tag


class ReleaseVersionTests(unittest.TestCase):
    def test_supported_tags(self):
        self.assertEqual(parse_release_tag("1.2.3"), "1.2.3")
        self.assertEqual(parse_release_tag("v1.2.3"), "1.2.3")
        self.assertEqual(parse_release_tag("v1.2.3-beta12"), "1.2.3b12")

    def test_rejects_malformed_or_noncanonical_tags(self):
        for tag in ("01.2.3", "1.02.3", "1.2.3-beta0", "1.2.3-rc1", "1.2", "vv1.2.3", "1.2.3+local"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                parse_release_tag(tag)

    def test_publication_credentials_removed_from_build_environment(self):
        with patch.dict(os.environ, {"FORGEJO_PACKAGE_TOKEN": "secret", "TWINE_PASSWORD": "secret", "KEEP_ME": "yes"}):
            env = sanitized_environment()
        self.assertNotIn("FORGEJO_PACKAGE_TOKEN", env)
        self.assertNotIn("TWINE_PASSWORD", env)
        self.assertEqual(env["KEEP_ME"], "yes")

    def test_preflight_rejects_duplicate_or_unexpected_publication_contents(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "other.whl").touch()
            (root / "extra.tar.gz").touch()
            with self.assertRaises(ValueError):
                validate_artifacts("1.2.3", root)

class ArtifactValidationTests(unittest.TestCase):
    def make_pair(self, root):
        import io
        import tarfile
        import zipfile
        metadata = ('Metadata-Version: 2.4\nName: rpi-cc1101-transciever\n'
                    'Version: 1.2.3\nRequires-Python: >=3.10\n'
                    'Requires-Dist: cc1101==3.0.0\nRequires-Dist: spidev\n'
                    'Requires-Dist: rpi-lgpio\n\n')
        wheel = root / 'rpi_cc1101_transciever-1.2.3-py3-none-any.whl'
        with zipfile.ZipFile(wheel, 'w') as archive:
            archive.writestr('rpi_cc1101_transciever-1.2.3.dist-info/METADATA', metadata)
        sdist = root / 'rpi_cc1101_transciever-1.2.3.tar.gz'
        with tarfile.open(sdist, 'w:gz') as archive:
            data = metadata.encode()
            info = tarfile.TarInfo('rpi_cc1101_transciever-1.2.3/PKG-INFO')
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        return wheel, sdist

    def test_pair_metadata_and_provenance(self):
        import json
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pair = self.make_pair(root)
            self.assertEqual(len(validate_artifacts('v1.2.3', root)), 2)
            with self.assertRaises(ValueError):
                validate_artifacts('1.2.4', root)
            manifest = {'event_commit': 'a' * 40, 'tag': 'v1.2.3', 'version': '1.2.3',
                        'artifacts': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in pair}}
            (root / 'provenance.json').write_text(json.dumps(manifest))
            self.assertEqual(len(preflight('v1.2.3', root, 'a' * 40)), 2)
            with self.assertRaises(ValueError):
                preflight('v1.2.3', root, 'b' * 40)
            pair[0].write_bytes(pair[0].read_bytes() + b'tamper')
            with self.assertRaises(ValueError):
                preflight('v1.2.3', root, 'a' * 40)

    def test_build_subprocess_has_no_publication_credentials(self):
        from scripts.package_artifacts import build_artifacts
        import subprocess
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
            root = Path(source)
            (root / 'cc1101_transceiver').mkdir()
            (root / 'cc1101_transceiver/_version.py').write_text('__version__ = "0.1.0"\n')
            with patch.dict(os.environ, {'TWINE_PASSWORD': 'secret'}), patch('scripts.package_artifacts.subprocess.run') as run:
                run.side_effect = subprocess.CalledProcessError(1, 'build')
                with self.assertRaises(subprocess.CalledProcessError):
                    build_artifacts('1.2.3', root, output)
                self.assertNotIn('TWINE_PASSWORD', run.call_args.kwargs['env'])
                self.assertEqual((root / 'cc1101_transceiver/_version.py').read_text(), '__version__ = "0.1.0"\n')

    def test_metadata_body_and_dependency_contract(self):
        from scripts.package_artifacts import _metadata
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pair = self.make_pair(root)
            original = _metadata(pair[0])
            with patch('scripts.package_artifacts._metadata', return_value=original + 'Version: README example\n'):
                self.assertEqual(len(validate_artifacts('1.2.3', root)), 2)
            for old, new in [('cc1101==3.0.0', 'cc1101==3.0.0.post1'),
                             ('spidev', 'spidevil'), ('rpi-lgpio', 'rpi-lgpio-unrelated'),
                             ('spidev', 'spidev; python_version < "3.0"')]:
                with self.subTest(new=new), patch('scripts.package_artifacts._metadata', return_value=original.replace(old, new)):
                    with self.assertRaises(ValueError):
                        validate_artifacts('1.2.3', root)

    def test_workflow_propagates_duplicate_upload_failure(self):
        import subprocess
        workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/publish.yml').read_text()
        upload = workflow.split('name: Upload validated pair', 1)[1]
        command = upload.split('run: ', 1)[1].strip()
        self.assertNotIn('--skip-existing', command)
        self.assertEqual(command.count('twine upload'), 1)
        with tempfile.TemporaryDirectory() as temp:
            executable = Path(temp) / 'python'
            executable.write_text('#!/bin/sh\necho "duplicate package rejected" >&2\nexit 42\n')
            executable.chmod(0o755)
            result = subprocess.run(['bash', '-e', '-c', command], env={**os.environ, 'PATH': temp + os.pathsep + os.environ['PATH']}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 42)
            self.assertIn('duplicate package rejected', result.stderr)


if __name__ == "__main__":
    unittest.main()
