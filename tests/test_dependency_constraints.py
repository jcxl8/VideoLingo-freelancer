import unittest


class DependencyConstraintsTest(unittest.TestCase):
    def test_requirement_names_are_normalized_and_comments_ignored(self):
        from scripts.generate_constraints import requirement_names

        names = requirement_names(
            [
                "# comment",
                "OpenAI>=1.0,<2",
                "ruamel.yaml",
                "g2p-en[all]",
                "",
            ]
        )

        self.assertEqual(names, ["openai", "ruamel-yaml", "g2p-en"])

    def test_constraints_are_sorted_and_pinned(self):
        from scripts.generate_constraints import build_constraints

        constraints, missing = build_constraints(
            ["Pandas>=2", "numpy>=2", "missing-package"],
            {"numpy": "2.3.5", "pandas": "2.3.3"},
        )

        self.assertEqual(constraints, ["numpy==2.3.5", "pandas==2.3.3"])
        self.assertEqual(missing, ["missing-package"])


if __name__ == "__main__":
    unittest.main()
