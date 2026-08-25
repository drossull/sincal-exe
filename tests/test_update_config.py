import unittest

from sincal import resources as sincal_resource_sync
from sincal.update_config import (
    DISTRIBUTION_BRANCH,
    DISTRIBUTION_OWNER,
    DISTRIBUTION_RELEASES_URL,
    DISTRIBUTION_REPOSITORY,
    api_url,
)


class UpdateConfigurationTests(unittest.TestCase):
    def test_targets_the_separate_public_repository(self):
        self.assertEqual(DISTRIBUTION_OWNER, "drossull")
        self.assertEqual(DISTRIBUTION_REPOSITORY, "sincal-updates")
        self.assertEqual(DISTRIBUTION_BRANCH, "main")
        self.assertEqual(
            DISTRIBUTION_RELEASES_URL,
            "https://github.com/drossull/sincal-updates/releases",
        )
        self.assertEqual(
            api_url("releases/latest"),
            "https://api.github.com/repos/drossull/sincal-updates/releases/latest",
        )
        self.assertIn("drossull/sincal-updates", sincal_resource_sync._tree_url())


if __name__ == "__main__":
    unittest.main()
