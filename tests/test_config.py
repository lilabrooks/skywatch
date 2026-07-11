import unittest

from skywatch.config import DEFAULT_PORT, ConfigError, apply_env_file, load_config

VALID = {"LATITUDE": "47.61", "LONGITUDE": "-122.33"}


class ConfigAssertions(unittest.TestCase):
    def assert_error(self, env, *fragments):
        with self.assertRaises(ConfigError) as ctx:
            load_config(env)
        message = str(ctx.exception)
        for fragment in fragments:
            self.assertIn(fragment, message)
        return message


class LoadConfigTests(ConfigAssertions):
    def test_valid_minimal_env(self):
        config = load_config(VALID)
        self.assertEqual(config.latitude, 47.61)
        self.assertEqual(config.longitude, -122.33)
        self.assertEqual(config.port, DEFAULT_PORT)
        self.assertEqual(config.host, "127.0.0.1")

    def test_port_override(self):
        config = load_config({**VALID, "PORT": "9100"})
        self.assertEqual(config.port, 9100)

    def test_db_path_defaults(self):
        self.assertEqual(load_config(VALID).db_path, "skywatch.db")

    def test_db_path_override(self):
        config = load_config({**VALID, "DB_PATH": "state.db"})
        self.assertEqual(config.db_path, "state.db")

    def test_db_path_missing_directory_rejected(self):
        with self.assertRaises(ConfigError) as ctx:
            load_config({**VALID, "DB_PATH": "/no/such/dir/skywatch.db"})
        self.assertIn("DB_PATH", str(ctx.exception))
        self.assertIn("does not exist", str(ctx.exception))

    def test_extra_variables_ignored(self):
        config = load_config({**VALID, "SHELL": "/bin/zsh", "HOME": "/Users/x"})
        self.assertEqual(config.latitude, 47.61)

    def test_garbage_latitude_names_variable_and_format(self):
        self.assert_error(
            {**VALID, "LATITUDE": "banana"},
            "LATITUDE",
            "decimal degrees between -90 and 90",
            "'banana'",
        )

    def test_missing_longitude(self):
        env = dict(VALID)
        del env["LONGITUDE"]
        self.assert_error(env, "LONGITUDE", "required but not set", "-180 and 180")

    def test_empty_string_counts_as_unset(self):
        self.assert_error({**VALID, "LATITUDE": "  "}, "LATITUDE", "required but not set")

    def test_latitude_out_of_range(self):
        self.assert_error({**VALID, "LATITUDE": "95"}, "LATITUDE", "out of range")

    def test_longitude_out_of_range(self):
        self.assert_error({**VALID, "LONGITUDE": "-190"}, "LONGITUDE", "out of range")

    def test_nan_and_inf_rejected(self):
        self.assert_error({**VALID, "LATITUDE": "nan"}, "LATITUDE", "out of range")
        self.assert_error({**VALID, "LONGITUDE": "inf"}, "LONGITUDE", "out of range")

    def test_port_garbage(self):
        self.assert_error({**VALID, "PORT": "web"}, "PORT", "integer between 1 and 65535", "'web'")

    def test_port_out_of_range(self):
        self.assert_error({**VALID, "PORT": "0"}, "PORT", "out of range")
        self.assert_error({**VALID, "PORT": "70000"}, "PORT", "out of range")

    def test_all_errors_collected_in_one_failure(self):
        message = self.assert_error(
            {"LATITUDE": "banana", "PORT": "web"}, "LATITUDE", "LONGITUDE", "PORT"
        )
        self.assertEqual(len(message.strip().splitlines()), 3)


class ThresholdConfigTests(ConfigAssertions):
    def test_defaults(self):
        config = load_config(VALID)
        self.assertEqual(config.cloud_go_max, 30)
        self.assertEqual(config.cloud_maybe_max, 70)
        self.assertEqual(config.min_elevation_deg, 25.0)

    def test_overrides(self):
        config = load_config(
            {**VALID, "CLOUD_GO_MAX": "20", "CLOUD_MAYBE_MAX": "80", "MIN_ELEVATION_DEG": "30"}
        )
        self.assertEqual(config.cloud_go_max, 20)
        self.assertEqual(config.cloud_maybe_max, 80)
        self.assertEqual(config.min_elevation_deg, 30.0)

    def test_garbage_percentage_rejected(self):
        self.assert_error({**VALID, "CLOUD_GO_MAX": "cloudy"}, "CLOUD_GO_MAX", "percentage")
        self.assert_error({**VALID, "CLOUD_MAYBE_MAX": "110"}, "CLOUD_MAYBE_MAX", "out of range")

    def test_garbage_elevation_rejected(self):
        self.assert_error({**VALID, "MIN_ELEVATION_DEG": "high"}, "MIN_ELEVATION_DEG", "degrees")
        self.assert_error({**VALID, "MIN_ELEVATION_DEG": "95"}, "MIN_ELEVATION_DEG", "out of range")

    def test_maybe_threshold_must_not_undercut_go(self):
        self.assert_error(
            {**VALID, "CLOUD_GO_MAX": "50", "CLOUD_MAYBE_MAX": "20"},
            "CLOUD_MAYBE_MAX",
            ">= CLOUD_GO_MAX",
        )


class ApplyEnvFileTests(unittest.TestCase):
    def apply(self, text, environ=None):
        import tempfile
        from pathlib import Path

        environ = {} if environ is None else environ
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text(text)
            applied = apply_env_file(environ, str(path))
        return environ, applied

    def test_fills_unset_keys_only(self):
        environ, applied = self.apply(
            "LATITUDE=1\nLONGITUDE=2\n", environ={"LATITUDE": "kept"}
        )
        self.assertEqual(environ, {"LATITUDE": "kept", "LONGITUDE": "2"})
        self.assertEqual(applied, ["LONGITUDE"])

    def test_blank_environ_value_does_not_shadow_the_file(self):
        # `export LATITUDE=` in the shell must not defeat a good .env value.
        environ, applied = self.apply(
            "LATITUDE=47.61\nLONGITUDE=-122.33\n",
            environ={"LATITUDE": "", "LONGITUDE": "   "},
        )
        self.assertEqual(environ["LATITUDE"], "47.61")
        self.assertEqual(environ["LONGITUDE"], "-122.33")
        self.assertEqual(sorted(applied), ["LATITUDE", "LONGITUDE"])

    def test_ignores_comments_blanks_and_junk(self):
        environ, applied = self.apply("# comment\n\nnot a pair\nPORT=9000\n")
        self.assertEqual(environ, {"PORT": "9000"})
        self.assertEqual(applied, ["PORT"])

    def test_strips_quotes_and_export_prefix(self):
        environ, _ = self.apply("export SMTP_FROM='sky@local'\nSMTP_TO=\"o@e.org\"\n")
        self.assertEqual(environ["SMTP_FROM"], "sky@local")
        self.assertEqual(environ["SMTP_TO"], "o@e.org")

    def test_missing_file_is_not_an_error(self):
        environ = {}
        self.assertEqual(apply_env_file(environ, "/no/such/.env"), [])
        self.assertEqual(environ, {})


class OperationsConfigTests(ConfigAssertions):
    def test_defaults(self):
        config = load_config(VALID)
        self.assertEqual(config.fetch_interval_minutes, 360)
        self.assertEqual(config.retention_days, 30)
        self.assertIsNone(config.quiet_hours)

    def test_overrides(self):
        from datetime import time

        config = load_config(
            {
                **VALID,
                "FETCH_INTERVAL_MINUTES": "30",
                "RETENTION_DAYS": "90",
                "QUIET_HOURS": "22:00-08:00",
            }
        )
        self.assertEqual(config.fetch_interval_minutes, 30)
        self.assertEqual(config.retention_days, 90)
        self.assertEqual(config.quiet_hours, (time(22, 0), time(8, 0)))

    def test_interval_bounds(self):
        self.assert_error({**VALID, "FETCH_INTERVAL_MINUTES": "1"}, "FETCH_INTERVAL_MINUTES", "out of range")
        self.assert_error({**VALID, "FETCH_INTERVAL_MINUTES": "hourly"}, "FETCH_INTERVAL_MINUTES", "minutes")

    def test_retention_garbage(self):
        self.assert_error({**VALID, "RETENTION_DAYS": "forever"}, "RETENTION_DAYS", "days")

    def test_quiet_hours_garbage_names_format(self):
        self.assert_error({**VALID, "QUIET_HOURS": "night"}, "QUIET_HOURS", "22:00-08:00")
        self.assert_error({**VALID, "QUIET_HOURS": "25:00-08:00"}, "QUIET_HOURS", "not a valid time window")

    def test_quiet_hours_equal_endpoints_rejected(self):
        self.assert_error({**VALID, "QUIET_HOURS": "08:00-08:00"}, "QUIET_HOURS", "equal")


class SmtpConfigTests(ConfigAssertions):
    def test_unset_means_digest_disabled(self):
        self.assertIsNone(load_config(VALID).smtp)

    def test_minimal_smtp_with_defaults(self):
        config = load_config(
            {**VALID, "SMTP_HOST": "127.0.0.1", "SMTP_TO": "owner@example.org"}
        )
        smtp = config.smtp
        self.assertIsNotNone(smtp)
        self.assertEqual(smtp.host, "127.0.0.1")
        self.assertEqual(smtp.port, 1025)
        self.assertEqual(smtp.sender, "skywatch@localhost")
        self.assertEqual(smtp.recipient, "owner@example.org")
        self.assertIsNone(smtp.user)
        self.assertFalse(smtp.starttls)

    def test_full_smtp(self):
        config = load_config(
            {
                **VALID,
                "SMTP_HOST": "smtp.example.org",
                "SMTP_PORT": "587",
                "SMTP_TO": "owner@example.org",
                "SMTP_FROM": "iss@example.org",
                "SMTP_USER": "iss",
                "SMTP_PASSWORD": "hunter2",
                "SMTP_STARTTLS": "yes",
            }
        )
        smtp = config.smtp
        self.assertEqual(smtp.port, 587)
        self.assertEqual(smtp.sender, "iss@example.org")
        self.assertEqual(smtp.user, "iss")
        self.assertTrue(smtp.starttls)

    def test_password_never_in_repr(self):
        config = load_config(
            {
                **VALID,
                "SMTP_HOST": "smtp.example.org",
                "SMTP_TO": "o@e.org",
                "SMTP_USER": "iss",
                "SMTP_PASSWORD": "hunter2",
            }
        )
        self.assertNotIn("hunter2", repr(config))
        self.assertNotIn("hunter2", repr(config.smtp))

    def test_to_without_host_rejected(self):
        self.assert_error({**VALID, "SMTP_TO": "o@e.org"}, "SMTP_HOST", "required when SMTP_TO")

    def test_host_without_to_rejected(self):
        self.assert_error({**VALID, "SMTP_HOST": "127.0.0.1"}, "SMTP_TO", "required when SMTP_HOST")

    def test_user_without_password_rejected(self):
        self.assert_error(
            {**VALID, "SMTP_HOST": "h", "SMTP_TO": "o@e.org", "SMTP_USER": "iss"},
            "SMTP_USER/SMTP_PASSWORD",
        )

    def test_source_base_urls_default_to_real_upstreams(self):
        config = load_config(VALID)
        self.assertTrue(config.passes_base_url.startswith("https://sat.terrestre.ar/"))
        self.assertTrue(config.forecast_base_url.startswith("https://api.open-meteo.com/"))

    def test_source_base_urls_overridable_for_fixture_servers(self):
        config = load_config(
            {
                **VALID,
                "PASSES_BASE_URL": "http://127.0.0.1:9999/passes.json",
                "FORECAST_BASE_URL": "http://127.0.0.1:9999/forecast.json",
            }
        )
        self.assertEqual(config.passes_base_url, "http://127.0.0.1:9999/passes.json")
        self.assertEqual(config.forecast_base_url, "http://127.0.0.1:9999/forecast.json")

    def test_non_http_base_url_rejected(self):
        self.assert_error(
            {**VALID, "PASSES_BASE_URL": "ftp://example.org/passes"},
            "PASSES_BASE_URL",
            "http(s)",
        )

    def test_garbage_starttls_rejected(self):
        self.assert_error(
            {**VALID, "SMTP_HOST": "h", "SMTP_TO": "o@e.org", "SMTP_STARTTLS": "banana"},
            "SMTP_STARTTLS",
            "yes/no",
        )


if __name__ == "__main__":
    unittest.main()
