from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "system_status_monitor" / "app" / "templates" / "index.html"


class DashboardTemplateTest(unittest.TestCase):
    def setUp(self):
        self.template = TEMPLATE.read_text(encoding="utf-8")

    def test_reference_layout_sections_are_present(self):
        self.assertIn('class="app-title"', self.template)
        self.assertIn('class="runtime-card"', self.template)
        self.assertIn('class="health-card"', self.template)
        self.assertIn('class="metric-card-grid"', self.template)
        self.assertIn("<title>系统状态</title>", self.template)
        self.assertIn('<h1 class="app-title">系统状态</h1>', self.template)
        self.assertIn('class="header-bar"', self.template)
        self.assertIn('class="app-subtitle"', self.template)
        self.assertIn("Home Assistant 系统运行状态及健康评分", self.template)
        self.assertIn('id="refreshBtn"', self.template)
        self.assertNotIn("刷新间隔", self.template)

    def test_metric_grid_matches_desktop_and_mobile_references(self):
        self.assertNotIn("磁盘寿命", self.template)
        self.assertNotIn("stats.disk_health", self.template)
        self.assertNotIn("SMART", self.template)
        self.assertRegex(
            self.template,
            re.compile(
                r"\.metric-card-grid\s*\{[^}]*grid-template-columns:\s*repeat\(6,",
                re.S,
            ),
        )
        self.assertIn("系统负载", self.template)
        self.assertIn('"metric-group-primary"', self.template)
        self.assertIn('"metric-group-secondary"', self.template)
        self.assertIn("metrics.slice(0, 3)", self.template)
        self.assertIn("metrics.slice(3)", self.template)
        self.assertIn("CPU温度", self.template)
        self.assertIn('title: "温度"', self.template)
        self.assertIn('subtitle: "CPU"', self.template)
        self.assertIn('var preferredOrder = ["CPU", "CPU温度", "系统负载", "响应延迟", "内存", "磁盘"];', self.template)

    def test_requested_visual_tuning_is_encoded_in_template(self):
        self.assertRegex(self.template, r"color-scheme:\s*light dark;")
        self.assertRegex(self.template, r"--page:\s*#fafafa;")
        self.assertRegex(self.template, r"--card:\s*#ffffff;")
        self.assertRegex(self.template, r"--card-border:\s*#d8d8d8;")
        self.assertRegex(self.template, r"--card-shadow:\s*0 1px 2px rgba\(0,\s*0,\s*0,\s*0\.04\);")
        self.assertRegex(self.template, r"--radius:\s*12px;")
        self.assertRegex(
            self.template,
            re.compile(
                r"body\s*\{[^}]*padding:\s*18px clamp\(30px,\s*4vw,\s*64px\) 30px;",
                re.S,
            ),
        )
        self.assertRegex(
            self.template,
            re.compile(
                r"\.app-title\s*\{[^}]*font-size:\s*22px;[^}]*font-weight:\s*600;[^}]*letter-spacing:\s*0\.5px;[^}]*color:\s*#ffffff;",
                re.S,
            ),
        )
        self.assertRegex(
            self.template,
            re.compile(
                r"\.app-subtitle\s*\{[^}]*color:\s*#9a9a9a;[^}]*font-size:\s*12px;",
                re.S,
            ),
        )
        self.assertRegex(
            self.template,
            re.compile(
                r"\.score-value\s*\{[^}]*font-size:\s*clamp\(2\.33rem,\s*3vw,\s*3\.15rem\);[^}]*font-weight:\s*800;",
                re.S,
            ),
        )
        self.assertRegex(
            self.template,
            re.compile(
                r"\.runtime-card,\s*\.health-card,\s*\.metric-card-grid,\s*\.metric-group\s*\{[^}]*border:\s*1px solid var\(--card-border\);[^}]*box-shadow:\s*var\(--card-shadow\);",
                re.S,
            ),
        )
        self.assertNotIn("backdrop-filter:", self.template)
        non_title_css = re.sub(
            r"\.(?:app-title|score-value)\s*\{[^}]*\}",
            "",
            self.template,
            flags=re.S,
        )
        self.assertNotIn("font-weight:", non_title_css)
        self.assertRegex(
            self.template,
            re.compile(
                r"\.dashboard-shell\s*\{[^}]*max-width:\s*1378px;",
                re.S,
            ),
        )
        self.assertNotIn("zoom:", self.template)
        self.assertNotIn("scale(", self.template)
        self.assertRegex(
            self.template,
            re.compile(
                r"\.runtime-value\s*\{[^}]*color:\s*var\(--text\);",
                re.S,
            ),
        )
        self.assertRegex(
            self.template,
            re.compile(
                r"\.dim-label\s*\{[^}]*color:\s*var\(--text\);",
                re.S,
            ),
        )
        self.assertRegex(
            self.template,
            re.compile(
                r"\.metric-title\s*\{[^}]*color:\s*var\(--text\);",
                re.S,
            ),
        )
        self.assertNotIn("-- 秒", self.template)
        self.assertNotIn("+ s + \" 秒\"", self.template)

    def test_theme_follows_system_color_scheme(self):
        self.assertRegex(
            self.template,
            re.compile(
                r"@media \(prefers-color-scheme:\s*dark\)\s*\{[^}]*:root\s*\{[^}]*"
                r"--page:\s*#111111;[^}]*"
                r"--card:\s*#181818;[^}]*"
                r"--card-border:\s*#363636;[^}]*"
                r"--card-shadow:\s*none;[^}]*"
                r"--text:\s*#e8e8e8;[^}]*"
                r"--muted:\s*#a0a0a0;[^}]*"
                r"--soft:\s*#232b26;",
                re.S,
            ),
        )
        self.assertRegex(self.template, r"--score-label:\s*#626874;")
        self.assertRegex(self.template, r"--metric-value:\s*#707684;")
        self.assertRegex(self.template, r"--subtitle:\s*#9aa0aa;")
        self.assertRegex(
            self.template,
            re.compile(r"\.score-label\s*\{[^}]*color:\s*var\(--score-label\);", re.S),
        )
        self.assertRegex(
            self.template,
            re.compile(r"\.metric-value\s*\{[^}]*color:\s*var\(--metric-value\);", re.S),
        )
        self.assertRegex(
            self.template,
            re.compile(r"\.metric-subtitle\s*\{[^}]*color:\s*var\(--subtitle\);", re.S),
        )

    def test_metric_titles_match_health_label_font_size(self):
        self.assertRegex(
            self.template,
            re.compile(
                r"\.dim-label\s*\{[^}]*font-size:\s*clamp\(0\.92rem,\s*0\.99vw,\s*1\.14rem\);[^}]*\}"
                r".*\.metric-title\s*\{[^}]*font-size:\s*clamp\(0\.92rem,\s*0\.99vw,\s*1\.14rem\);",
                re.S,
            ),
        )
        self.assertRegex(
            self.template,
            re.compile(
                r"@media \(max-width:\s*980px\)\s*\{.*\.dim-label\s*\{[^}]*font-size:\s*0\.99rem;[^}]*\}"
                r".*\.metric-title\s*\{[^}]*font-size:\s*0\.99rem;",
                re.S,
            ),
        )
        self.assertRegex(
            self.template,
            re.compile(
                r"@media \(max-width:\s*560px\)\s*\{.*\.dim-label\s*\{[^}]*font-size:\s*0\.86rem;[^}]*\}"
                r".*\.metric-title\s*\{[^}]*font-size:\s*0\.86rem;",
                re.S,
            ),
        )

    def test_color_thresholds_match_requested_status_rules(self):
        self.assertRegex(
            self.template,
            re.compile(
                r"function colorForScore\(score\)\s*\{[^}]*"
                r"if \(number >= 80\) return \"#19be5d\";[^}]*"
                r"if \(number >= 60\) return \"#f97316\";[^}]*"
                r"return \"#e8453c\";",
                re.S,
            ),
        )
        self.assertRegex(
            self.template,
            re.compile(
                r"function colorForPercentMetric\(value\)\s*\{[^}]*"
                r"if \(number > 90\) return \"#e8453c\";[^}]*"
                r"if \(number > 60\) return \"#f97316\";[^}]*"
                r"return \"#19be5d\";",
                re.S,
            ),
        )
        self.assertRegex(
            self.template,
            re.compile(
                r"function colorForLatency\(value\)\s*\{[^}]*"
                r"if \(number > 300\) return \"#e8453c\";[^}]*"
                r"if \(number > 100\) return \"#f97316\";[^}]*"
                r"return \"#19be5d\";",
                re.S,
            ),
        )
        self.assertRegex(
            self.template,
            re.compile(
                r"function colorForTemperature\(value\)\s*\{[^}]*"
                r"if \(number >= 80\) return \"#e8453c\";[^}]*"
                r"if \(number > 60\) return \"#f97316\";[^}]*"
                r"return \"#19be5d\";",
                re.S,
            ),
        )
        self.assertIn("var scoreColor = colorForScore(score.total);", self.template)
        self.assertIn("color: colorForPercentMetric(Number(cpu.percent || 0))", self.template)
        self.assertIn("color: temp === null || temp === undefined ? \"#9aa0aa\" : colorForTemperature(Number(temp))", self.template)
        self.assertIn("color: hasLoad ? colorForPercentMetric(rawLoadPercent) : \"#9aa0aa\"", self.template)
        self.assertIn("color: latencyValue === null || latencyValue === undefined ? \"#9aa0aa\" : colorForLatency(Number(latencyValue))", self.template)
        self.assertIn("color: colorForPercentMetric(Number(mem.percent || 0))", self.template)
        self.assertIn("color: colorForPercentMetric(Number(disk.percent || 0))", self.template)

    def test_metric_ring_values_are_rounded_to_integers(self):
        self.assertRegex(
            self.template,
            re.compile(
                r"function formatMetricInteger\(value,\s*fallback\)\s*\{[^}]*"
                r"var number = Number\(value\);[^}]*"
                r"if \(!Number\.isFinite\(number\)\) return fallback \|\| \"N/A\";[^}]*"
                r"return String\(Math\.round\(number\)\);",
                re.S,
            ),
        )
        self.assertIn('value: formatMetricInteger(cpu.percent, "N/A") + "%"', self.template)
        self.assertIn('value: temp === null || temp === undefined ? "N/A" : formatMetricInteger(temp) + "°"', self.template)
        self.assertIn('value: hasLoad ? formatMetricInteger(rawLoadPercent) + "%" : "N/A"', self.template)
        self.assertIn('value: latencyValue === null || latencyValue === undefined ? "--" : formatMetricInteger(latencyValue) + "ms"', self.template)
        self.assertIn('value: formatMetricInteger(mem.percent, "N/A") + "%"', self.template)
        self.assertIn('value: disk.percent === null || disk.percent === undefined ? "N/A" : formatMetricInteger(disk.percent) + "%"', self.template)

    def test_mobile_metrics_split_into_two_cards(self):
        self.assertIn("@media (max-width: 700px)", self.template)
        self.assertRegex(self.template, r"--mobile-card-gap:\s*18px;")
        self.assertRegex(self.template, r"--mobile-card-gap:\s*14px;")
        self.assertRegex(
            self.template,
            re.compile(
                r"\.metric-card-grid\s*\{[^}]*background:\s*transparent;[^}]*display:\s*grid;[^}]*gap:\s*var\(--mobile-card-gap\);",
                re.S,
            ),
        )
        self.assertRegex(
            self.template,
            re.compile(
                r"\.metric-group-primary\s*\{[^}]*grid-template-columns:\s*repeat\(3,",
                re.S,
            ),
        )
        self.assertRegex(
            self.template,
            re.compile(
                r"\.metric-group-secondary\s*\{[^}]*grid-template-columns:\s*repeat\(3,",
                re.S,
            ),
        )


if __name__ == "__main__":
    unittest.main()
