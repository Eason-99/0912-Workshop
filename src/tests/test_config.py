"""测试唯一配置文件的加载和路径校验。首次覆盖：S0。"""

from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from core.config import ConfigError, load_config


class ConfigTests(unittest.TestCase):
    """在不调用外部服务时验证零参数配置约束。首次覆盖：S0。"""

    def test_repository_config_loads(self) -> None:
        """确认仓库内唯一配置可以成功加载。首次覆盖：S0。"""

        config = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
        self.assertEqual(config.stage, "s0_api")

    def test_output_path_cannot_escape_src(self) -> None:
        """确认运行目录不能越过配置所在的 `src` 根目录。首次覆盖：S0。"""

        source = (Path(__file__).resolve().parents[1] / "config.yaml").read_text(encoding="utf-8")
        invalid = source.replace("output_dir: runs", "output_dir: ../outside")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.yaml"
            path.write_text(invalid, encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_third_party_profile_reads_connection_from_dotenv(self) -> None:
        """确认第三方 profile 的 URL 和 Key 均从指定 `.env` 读取。首次覆盖：S0。"""

        repository_config = Path(__file__).resolve().parents[1] / "config.yaml"
        source = repository_config.read_text(encoding="utf-8")
        source = source.replace("active_profile: deepseek", "active_profile: third_party")
        source = source.replace("THIRD_PARTY_API_KEY", "TEST_THIRD_PARTY_API_KEY")
        source = source.replace("THIRD_PARTY_BASE_URL", "TEST_THIRD_PARTY_BASE_URL")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "core").mkdir()
            (root / "config.yaml").write_text(source, encoding="utf-8")
            (root / "core" / ".env").write_text(
                "TEST_THIRD_PARTY_API_KEY=test-key\n"
                "TEST_THIRD_PARTY_BASE_URL=https://gateway.example.com/v1/\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                config = load_config(root / "config.yaml")
                api_key, base_url = config.model_connection()
        self.assertEqual(api_key, "test-key")
        self.assertEqual(base_url, "https://gateway.example.com/v1")

    def test_model_env_path_cannot_escape_src(self) -> None:
        """确认私密配置文件路径不能指向越过 `src` 根目录。首次覆盖：S0。"""

        source = (Path(__file__).resolve().parents[1] / "config.yaml").read_text(encoding="utf-8")
        invalid = source.replace("env_file: core/.env", "env_file: ../outside/.env")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.yaml"
            path.write_text(invalid, encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
