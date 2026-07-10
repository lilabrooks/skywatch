import unittest

from skywatch.config import DEFAULT_PORT, ConfigError, load_config

VALID = {"LATITUDE": "47.61", "LONGITUDE": "-122.33"}


class LoadConfigTests(unittest.TestCase):
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

    def assert_error(self, env, *fragments):
        with self.assertRaises(ConfigError) as ctx:
            load_config(env)
        message = str(ctx.exception)
        for fragment in fragments:
            self.assertIn(fragment, message)
        return message

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


if __name__ == "__main__":
    unittest.main()
