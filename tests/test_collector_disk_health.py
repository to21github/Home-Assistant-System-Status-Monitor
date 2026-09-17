import sys
import types
import unittest
from pathlib import Path
from unittest.mock import mock_open, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "system_status_monitor" / "app"))

sys.modules.setdefault("psutil", types.ModuleType("psutil"))

import collector


class CollectorMetricsTest(unittest.TestCase):
    def test_meminfo_memory_uses_total_minus_available(self):
        meminfo = "\n".join(
            [
                "MemTotal:        4194304 kB",
                "MemFree:          524288 kB",
                "MemAvailable:    2621440 kB",
            ]
        )

        with patch("builtins.open", mock_open(read_data=meminfo)):
            memory = collector._read_memory_from_meminfo("/proc/meminfo")

        self.assertEqual(memory["total"], 4.0)
        self.assertEqual(memory["used"], 1.5)
        self.assertEqual(memory["free"], 2.5)
        self.assertEqual(memory["percent"], 37.5)
        self.assertEqual(memory["source"], "proc_meminfo")

    def test_supervisor_host_info_supplies_real_host_disk_usage(self):
        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "result": "ok",
                    "data": {
                        "disk_total": 57.8,
                        "disk_used": 14.0,
                        "disk_free": 43.8,
                    },
                }

        with patch.dict("os.environ", {"SUPERVISOR_TOKEN": "token"}, clear=False):
            with patch("collector.requests.get", return_value=FakeResponse()) as get:
                disks = collector._collect_host_disks()

        self.assertEqual(
            disks,
            [
                {
                    "mount": "host",
                    "total": 57.8,
                    "used": 14.0,
                    "free": 43.8,
                    "percent": 24.2,
                    "source": "supervisor_host_info",
                }
            ],
        )
        get.assert_called_once()
        self.assertEqual(get.call_args.args[0], "http://supervisor/host/info")

    def test_statvfs_data_disk_supplies_data_partition_usage(self):
        class FakeStatvfs:
            f_frsize = 4096
            f_blocks = 16 * 1024 * 1024   # 64 GB
            f_bavail = 12 * 1024 * 1024   # 48 GB 可用

        with patch("collector.os.statvfs", return_value=FakeStatvfs()) as statvfs:
            disks = collector._collect_data_disk()

        self.assertEqual(
            disks,
            [
                {
                    "mount": "/data",
                    "total": 64.0,
                    "used": 16.0,
                    "free": 48.0,
                    "percent": 25.0,
                    "source": "statvfs_data",
                }
            ],
        )
        statvfs.assert_called_once_with("/data")

    def test_statvfs_failure_returns_empty_for_fallback(self):
        with patch("collector.os.statvfs", side_effect=OSError("No such file or directory")):
            disks = collector._collect_data_disk()

        self.assertEqual(disks, [])

    def test_disk_collection_prefers_statvfs_before_supervisor(self):
        with patch("collector._collect_data_disk", return_value=[{
            "mount": "/data",
            "total": 64.0,
            "used": 16.0,
            "free": 48.0,
            "percent": 25.0,
            "source": "statvfs_data",
        }]) as data_disk:
            with patch("collector._collect_host_disks", return_value=[{
                "mount": "host",
                "total": 57.8,
                "used": 14.0,
                "free": 43.8,
                "percent": 24.2,
                "source": "supervisor_host_info",
            }]) as host_info:
                disks = collector._collect_disks()

        self.assertEqual(disks[0]["source"], "statvfs_data")
        data_disk.assert_called_once()
        host_info.assert_not_called()

    def test_disk_collection_falls_back_to_supervisor_when_statvfs_fails(self):
        with patch("collector._collect_data_disk", return_value=[]):
            with patch("collector._collect_host_disks", return_value=[{
                "mount": "host",
                "total": 57.8,
                "used": 14.0,
                "free": 43.8,
                "percent": 24.2,
                "source": "supervisor_host_info",
            }]) as host_info:
                disks = collector._collect_disks()

        self.assertEqual(disks[0]["source"], "supervisor_host_info")
        host_info.assert_called_once()

    def test_collected_stats_do_not_include_disk_life_payload(self):
        collector._cache = None
        with patch("collector._collect_memory", return_value={
            "total": 4.0,
            "used": 1.0,
            "free": 3.0,
            "percent": 25.0,
            "source": "test",
        }):
            with patch("collector._collect_disks", return_value=[{
                "mount": "host",
                "total": 64.0,
                "used": 16.0,
                "free": 48.0,
                "percent": 25.0,
                "source": "test",
            }]):
                with patch("collector.psutil.cpu_percent", return_value=12.5, create=True), \
                    patch("collector.psutil.cpu_count", return_value=4, create=True), \
                    patch("collector.psutil.getloadavg", return_value=(0.2, 0.3, 0.4), create=True), \
                    patch("collector.psutil.boot_time", return_value=1000, create=True), \
                    patch("collector.time.time", return_value=2000), \
                    patch("collector._get_cpu_temp", return_value=42.0):
                    stats = collector._do_collect()

        self.assertNotIn("disk_health", stats)


if __name__ == "__main__":
    unittest.main()
