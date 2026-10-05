import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile

from main import main, _is_srt_input
from vid2sub.subtitle_generator import SubtitleGenerator


class TestReferenceFeature(unittest.TestCase):
    def test_is_srt_input(self):
        self.assertTrue(_is_srt_input("test.srt"))
        self.assertTrue(_is_srt_input("/path/to/test.SRT"))
        self.assertFalse(_is_srt_input("https://youtu.be/xyz"))
        self.assertFalse(_is_srt_input("video.mp4"))

    def test_load_reference_file(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".txt", delete=False) as tf:
            tf.write("OBD2, CAN bus, ELM327")
            tf.flush()
            temp_path = tf.name

        try:
            content = SubtitleGenerator.load_reference(temp_path)
            self.assertEqual(content, "OBD2, CAN bus, ELM327")
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @patch("vid2sub.subtitle_generator.OpenAiSrtProcessor")
    def test_apply_llm_stages_reference_polish(self, mock_processor_cls):
        mock_processor = MagicMock()
        mock_processor_cls.return_value = mock_processor
        mock_processor.polish.return_value = "1\n00:00:01,000 --> 00:00:02,000\nPolished text\n"

        with tempfile.NamedTemporaryFile("w+", suffix=".md", delete=False) as tf:
            tf.write("# Glossary\nCAN bus protocol")
            tf.flush()
            ref_path = tf.name

        try:
            gen = SubtitleGenerator()
            gen.llm_api_url = "http://fake-llm:8000/v1"
            initial_srt = "1\n00:00:01,000 --> 00:00:02,000\nRaw text\n"

            result = gen._apply_llm_stages(
                initial_srt,
                language="ko",
                temp_path=None,
                reference=ref_path,
            )

            mock_processor.polish.assert_called_once()
            call_args = mock_processor.polish.call_args[0]
            self.assertEqual(call_args[0], initial_srt)
            self.assertIn("CAN bus protocol", call_args[1])
            self.assertEqual(result, "1\n00:00:01,000 --> 00:00:02,000\nPolished text\n")
        finally:
            Path(ref_path).unlink(missing_ok=True)

    @patch("main.SubtitleGenerator")
    def test_cli_reference_flags(self, mock_gen_cls):
        mock_gen = MagicMock()
        mock_gen_cls.return_value = mock_gen

        # Test -r flag
        with patch("sys.argv", ["main.py", "video.mp4", "-r", "ref.txt"]):
            main()
            mock_gen.process.assert_called_once()
            self.assertEqual(mock_gen.process.call_args[1]["reference"], "ref.txt")

        mock_gen.reset_mock()

        # Test --ref flag
        with patch("sys.argv", ["main.py", "video.mp4", "--ref", "ref.txt"]):
            main()
            mock_gen.process.assert_called_once()
            self.assertEqual(mock_gen.process.call_args[1]["reference"], "ref.txt")

        mock_gen.reset_mock()

        # Test --reference flag
        with patch("sys.argv", ["main.py", "video.mp4", "--reference", "ref.txt"]):
            main()
            mock_gen.process.assert_called_once()
            self.assertEqual(mock_gen.process.call_args[1]["reference"], "ref.txt")

        mock_gen.reset_mock()

        # Test legacy -p flag
        with patch("sys.argv", ["main.py", "video.mp4", "-p", "ref.txt"]):
            main()
            mock_gen.process.assert_called_once()
            self.assertEqual(mock_gen.process.call_args[1]["reference"], "ref.txt")

    @patch("main.SubtitleGenerator")
    def test_cli_srt_input_with_reference(self, mock_gen_cls):
        mock_gen = MagicMock()
        mock_gen_cls.return_value = mock_gen
        mock_gen.process_srt_file.return_value = Path("test.srt")

        with patch("sys.argv", ["main.py", "test.srt", "-r", "ref.txt"]):
            main()
            mock_gen.process_srt_file.assert_called_once()
            self.assertEqual(mock_gen.process_srt_file.call_args[1]["reference"], "ref.txt")


if __name__ == "__main__":
    unittest.main()
