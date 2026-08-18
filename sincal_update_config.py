"""Configuración pública del canal de distribución de SINCAL."""

DISTRIBUTION_OWNER = "drossull"
DISTRIBUTION_REPOSITORY = "sincal-updates"
DISTRIBUTION_BRANCH = "main"

DISTRIBUTION_REPOSITORY_URL = (
    f"https://github.com/{DISTRIBUTION_OWNER}/{DISTRIBUTION_REPOSITORY}"
)
DISTRIBUTION_RELEASES_URL = f"{DISTRIBUTION_REPOSITORY_URL}/releases"


def api_url(path: str) -> str:
    suffix = path.lstrip("/")
    return (
        f"https://api.github.com/repos/{DISTRIBUTION_OWNER}/"
        f"{DISTRIBUTION_REPOSITORY}/{suffix}"
    )
