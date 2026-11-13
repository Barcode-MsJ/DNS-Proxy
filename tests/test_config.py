import pytest
from dnsproxy.config import ConfigError, load_config


def _write_files(root):
    (root / "ad_list.txt").write_text("ads.example.com\n", encoding="utf-8")
    (root / "sanction_list.txt").write_text("service.example.org\n", encoding="utf-8")


def test_loads_defaults_and_optional_bonus_fields(tmp_path):
    _write_files(tmp_path)
    (tmp_path / "config.txt").write_text(
        "upstream_ip=127.0.0.1\nupstream_port=5354\nsinkhole_ip=0.0.0.0\nproxy_ip=192.0.2.10\n"
        "ad_list_file=ad_list.txt\nsanction_list_file=sanction_list.txt\n", encoding="utf-8"
    )
    config = load_config(tmp_path)
    assert config.upstream_timeout_sec == 2
    assert config.local_ttl == 60
    assert config.cache_enabled is True
    assert config.real_dns_enabled is False
    assert config.cache_max_entries is None


def test_missing_required_key_is_config_error(tmp_path):
    _write_files(tmp_path)
    (tmp_path / "config.txt").write_text("upstream_ip=127.0.0.1\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="Missing required"):
        load_config(tmp_path)


def test_bad_ip_port_and_boolean_are_rejected(tmp_path):
    _write_files(tmp_path)
    base = "upstream_ip=127.0.0.1\nupstream_port=5354\nsinkhole_ip=0.0.0.0\nproxy_ip=192.0.2.10\nad_list_file=ad_list.txt\nsanction_list_file=sanction_list.txt\n"
    for tail, expected in [("upstream_port=70000\n", "upstream_port"), ("cache_enabled=yes\n", "cache_enabled"), ("sinkhole_ip=999.1.1.1\n", "sinkhole_ip")]:
        (tmp_path / "config.txt").write_text(base + tail, encoding="utf-8")
        with pytest.raises(ConfigError, match=expected):
            load_config(tmp_path)


def test_missing_list_file_is_config_error(tmp_path):
    (tmp_path / "config.txt").write_text(
        "upstream_ip=127.0.0.1\nupstream_port=5354\nsinkhole_ip=0.0.0.0\nproxy_ip=192.0.2.10\n"
        "ad_list_file=missing.txt\nsanction_list_file=sanction_list.txt\n", encoding="utf-8"
    )
    (tmp_path / "sanction_list.txt").write_text("", encoding="utf-8")
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path)


def test_real_dns_requires_public_resolver_and_port_53(tmp_path):
    _write_files(tmp_path)
    (tmp_path / "config.txt").write_text(
        "upstream_ip=127.0.0.1\nupstream_port=5354\nsinkhole_ip=0.0.0.0\nproxy_ip=192.0.2.10\n"
        "ad_list_file=ad_list.txt\nsanction_list_file=sanction_list.txt\nreal_dns_enabled=true\n", encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="real_dns_enabled"):
        load_config(tmp_path)


def test_non_finite_timeout_is_rejected(tmp_path):
    _write_files(tmp_path)
    (tmp_path / "config.txt").write_text(
        "upstream_ip=127.0.0.1\nupstream_port=5354\nsinkhole_ip=0.0.0.0\nproxy_ip=192.0.2.10\n"
        "ad_list_file=ad_list.txt\nsanction_list_file=sanction_list.txt\nupstream_timeout_sec=nan\n", encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="upstream_timeout_sec"):
        load_config(tmp_path)
