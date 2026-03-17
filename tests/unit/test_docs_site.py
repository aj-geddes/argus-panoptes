"""Tests for the GitHub Pages documentation site in docs/ directory.

RED phase: All tests should fail before the docs/ directory is created.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

DOCS_ROOT = Path(__file__).parent.parent.parent / "docs"

REQUIRED_MD_FILES = [
    "index.md",
    "getting-started.md",
    "api-reference.md",
    "architecture.md",
    "configuration.md",
    "sdk.md",
    "deployment.md",
    "user-guide.md",
    "contributing.md",
    "changelog.md",
]

REQUIRED_LAYOUT_FILES = [
    "_layouts/default.html",
    "_layouts/page.html",
]

REQUIRED_INCLUDE_FILES = [
    "_includes/head.html",
    "_includes/nav.html",
    "_includes/footer.html",
]

DARK_THEME_COLORS = [
    "#020617",  # slate-950 background
    "#0f172a",  # slate-900 card surface
    "#10b981",  # emerald accent
]


class TestDocsConfigExists:
    """Test that Jekyll configuration files exist with correct settings."""

    def test_config_yml_exists(self) -> None:
        """docs/_config.yml must exist."""
        config_path = DOCS_ROOT / "_config.yml"
        assert config_path.exists(), f"Missing: {config_path}"

    def test_config_yml_has_correct_baseurl(self) -> None:
        """docs/_config.yml must set baseurl to /argus-panoptes."""
        config_path = DOCS_ROOT / "_config.yml"
        assert config_path.exists(), "Missing _config.yml"
        with config_path.open() as f:
            config = yaml.safe_load(f)
        assert config.get("baseurl") == "/argus-panoptes", (
            f"Expected baseurl='/argus-panoptes', got {config.get('baseurl')!r}"
        )

    def test_config_yml_has_title(self) -> None:
        """docs/_config.yml must have a title."""
        config_path = DOCS_ROOT / "_config.yml"
        assert config_path.exists(), "Missing _config.yml"
        with config_path.open() as f:
            config = yaml.safe_load(f)
        assert "title" in config, "Missing 'title' in _config.yml"
        assert config["title"], "Title must be non-empty"

    def test_config_yml_has_url(self) -> None:
        """docs/_config.yml must have a url pointing to GitHub Pages."""
        config_path = DOCS_ROOT / "_config.yml"
        assert config_path.exists(), "Missing _config.yml"
        with config_path.open() as f:
            config = yaml.safe_load(f)
        assert "url" in config, "Missing 'url' in _config.yml"
        assert "github.io" in config.get("url", ""), "url should point to github.io"

    def test_config_yml_has_plugins(self) -> None:
        """docs/_config.yml must list SEO and sitemap plugins."""
        config_path = DOCS_ROOT / "_config.yml"
        assert config_path.exists(), "Missing _config.yml"
        with config_path.open() as f:
            config = yaml.safe_load(f)
        plugins = config.get("plugins", [])
        assert "jekyll-seo-tag" in plugins, "Missing jekyll-seo-tag plugin"
        assert "jekyll-sitemap" in plugins, "Missing jekyll-sitemap plugin"

    def test_gemfile_exists(self) -> None:
        """docs/Gemfile must exist with github-pages gem."""
        gemfile_path = DOCS_ROOT / "Gemfile"
        assert gemfile_path.exists(), f"Missing: {gemfile_path}"
        content = gemfile_path.read_text()
        assert "github-pages" in content, "Gemfile must include github-pages gem"


class TestRequiredMarkdownFiles:
    """Test that all required documentation pages exist."""

    @pytest.mark.parametrize("filename", REQUIRED_MD_FILES)
    def test_md_file_exists(self, filename: str) -> None:
        """Each required markdown documentation page must exist."""
        filepath = DOCS_ROOT / filename
        assert filepath.exists(), f"Missing documentation page: {filepath}"

    @pytest.mark.parametrize("filename", REQUIRED_MD_FILES)
    def test_md_file_has_front_matter(self, filename: str) -> None:
        """Each markdown page must have Jekyll front matter."""
        filepath = DOCS_ROOT / filename
        assert filepath.exists(), f"Missing: {filepath}"
        content = filepath.read_text()
        assert content.startswith("---"), f"{filename} must start with YAML front matter (---)"

    @pytest.mark.parametrize("filename", REQUIRED_MD_FILES)
    def test_md_file_has_title_in_front_matter(self, filename: str) -> None:
        """Each markdown page must declare a title in front matter."""
        filepath = DOCS_ROOT / filename
        assert filepath.exists(), f"Missing: {filepath}"
        content = filepath.read_text()
        # Extract front matter block
        parts = content.split("---", 2)
        assert len(parts) >= 3, f"{filename} front matter is malformed"
        front_matter = yaml.safe_load(parts[1])
        assert front_matter and "title" in front_matter, f"{filename} must have 'title' in front matter"

    def test_api_reference_has_curl_examples(self) -> None:
        """api-reference.md must contain curl command examples."""
        filepath = DOCS_ROOT / "api-reference.md"
        assert filepath.exists(), "Missing api-reference.md"
        content = filepath.read_text()
        assert "curl" in content, "api-reference.md must contain curl examples"

    def test_api_reference_has_all_endpoints(self) -> None:
        """api-reference.md must document all major API endpoints."""
        filepath = DOCS_ROOT / "api-reference.md"
        assert filepath.exists(), "Missing api-reference.md"
        content = filepath.read_text()
        required_endpoints = [
            "/health",
            "/v1/traces",
            "/api/v1/agents",
            "/api/v1/traces",
            "/api/v1/metrics/summary",
            "/api/v1/alerts",
            "/api/v1/config",
        ]
        for endpoint in required_endpoints:
            assert endpoint in content, f"api-reference.md missing endpoint: {endpoint}"

    def test_architecture_has_mermaid_diagrams(self) -> None:
        """architecture.md must contain Mermaid diagram blocks."""
        filepath = DOCS_ROOT / "architecture.md"
        assert filepath.exists(), "Missing architecture.md"
        content = filepath.read_text()
        assert "```mermaid" in content, "architecture.md must contain at least one mermaid code block"

    def test_architecture_has_multiple_diagrams(self) -> None:
        """architecture.md must contain multiple Mermaid diagrams."""
        filepath = DOCS_ROOT / "architecture.md"
        assert filepath.exists(), "Missing architecture.md"
        content = filepath.read_text()
        diagram_count = content.count("```mermaid")
        assert diagram_count >= 3, f"architecture.md should have at least 3 mermaid diagrams, found {diagram_count}"

    def test_configuration_documents_all_yaml_sections(self) -> None:
        """configuration.md must cover all config sections from argus.yaml."""
        filepath = DOCS_ROOT / "configuration.md"
        assert filepath.exists(), "Missing configuration.md"
        content = filepath.read_text()
        required_sections = [
            "server",
            "database",
            "ingestion",
            "metrics",
            "cost_model",
            "security",
            "alerts",
            "webhooks",
            "dashboard",
        ]
        for section in required_sections:
            assert section in content, f"configuration.md must document config section: {section}"

    def test_sdk_page_has_framework_examples(self) -> None:
        """sdk.md must show usage examples for major frameworks."""
        filepath = DOCS_ROOT / "sdk.md"
        assert filepath.exists(), "Missing sdk.md"
        content = filepath.read_text()
        required_frameworks = ["LangGraph", "CrewAI", "OpenAI"]
        for framework in required_frameworks:
            assert framework in content, f"sdk.md must include {framework} integration example"

    def test_getting_started_has_docker_quickstart(self) -> None:
        """getting-started.md must include a Docker quickstart."""
        filepath = DOCS_ROOT / "getting-started.md"
        assert filepath.exists(), "Missing getting-started.md"
        content = filepath.read_text()
        assert "docker" in content.lower(), "getting-started.md must include Docker instructions"
        assert "docker compose" in content.lower() or "docker-compose" in content.lower(), (
            "getting-started.md must include Docker Compose instructions"
        )


class TestLayoutFiles:
    """Test that Jekyll layout files exist with required content."""

    @pytest.mark.parametrize("filepath", REQUIRED_LAYOUT_FILES)
    def test_layout_file_exists(self, filepath: str) -> None:
        """Each required layout file must exist."""
        full_path = DOCS_ROOT / filepath
        assert full_path.exists(), f"Missing layout file: {full_path}"

    def test_default_layout_has_mermaid_script(self) -> None:
        """_layouts/default.html must include the Mermaid.js script tag."""
        layout_path = DOCS_ROOT / "_layouts/default.html"
        assert layout_path.exists(), "Missing _layouts/default.html"
        content = layout_path.read_text()
        assert "mermaid" in content.lower(), "_layouts/default.html must include Mermaid.js support"

    def test_default_layout_has_github_link(self) -> None:
        """_layouts/default.html must include a link to the GitHub repo."""
        layout_path = DOCS_ROOT / "_layouts/default.html"
        assert layout_path.exists(), "Missing _layouts/default.html"
        content = layout_path.read_text()
        assert "github.com/aj-geddes/argus-panoptes" in content, "_layouts/default.html must link to the GitHub repo"

    def test_default_layout_has_nav_include(self) -> None:
        """_layouts/default.html must include the nav partial."""
        layout_path = DOCS_ROOT / "_layouts/default.html"
        assert layout_path.exists(), "Missing _layouts/default.html"
        content = layout_path.read_text()
        assert "include nav.html" in content or "{% include nav.html" in content, (
            "_layouts/default.html must include nav.html"
        )

    def test_default_layout_has_head_include(self) -> None:
        """_layouts/default.html must include the head partial."""
        layout_path = DOCS_ROOT / "_layouts/default.html"
        assert layout_path.exists(), "Missing _layouts/default.html"
        content = layout_path.read_text()
        assert "include head.html" in content or "{% include head.html" in content, (
            "_layouts/default.html must include head.html"
        )

    def test_default_layout_has_footer_include(self) -> None:
        """_layouts/default.html must include the footer partial."""
        layout_path = DOCS_ROOT / "_layouts/default.html"
        assert layout_path.exists(), "Missing _layouts/default.html"
        content = layout_path.read_text()
        assert "include footer.html" in content or "{% include footer.html" in content, (
            "_layouts/default.html must include footer.html"
        )

    def test_page_layout_extends_default(self) -> None:
        """_layouts/page.html must extend the default layout."""
        layout_path = DOCS_ROOT / "_layouts/page.html"
        assert layout_path.exists(), "Missing _layouts/page.html"
        content = layout_path.read_text()
        assert "layout: default" in content or '"default"' in content, (
            "_layouts/page.html must extend the default layout"
        )


class TestIncludeFiles:
    """Test that Jekyll include partial files exist with correct content."""

    @pytest.mark.parametrize("filepath", REQUIRED_INCLUDE_FILES)
    def test_include_file_exists(self, filepath: str) -> None:
        """Each required include file must exist."""
        full_path = DOCS_ROOT / filepath
        assert full_path.exists(), f"Missing include file: {full_path}"

    def test_head_has_seo_tag(self) -> None:
        """_includes/head.html must include the Jekyll SEO tag."""
        head_path = DOCS_ROOT / "_includes/head.html"
        assert head_path.exists(), "Missing _includes/head.html"
        content = head_path.read_text()
        assert "seo" in content.lower(), "_includes/head.html must include Jekyll SEO tag"

    def test_head_has_canonical_css_link(self) -> None:
        """_includes/head.html must link to the main CSS file."""
        head_path = DOCS_ROOT / "_includes/head.html"
        assert head_path.exists(), "Missing _includes/head.html"
        content = head_path.read_text()
        assert "main.css" in content, "_includes/head.html must link to assets/css/main.css"

    def test_nav_has_all_doc_pages(self) -> None:
        """_includes/nav.html must link to all major documentation sections."""
        nav_path = DOCS_ROOT / "_includes/nav.html"
        assert nav_path.exists(), "Missing _includes/nav.html"
        content = nav_path.read_text()
        required_links = [
            "getting-started",
            "api-reference",
            "architecture",
            "configuration",
            "sdk",
            "deployment",
        ]
        for link in required_links:
            assert link in content, f"_includes/nav.html must link to {link}"

    def test_footer_has_github_link(self) -> None:
        """_includes/footer.html must include a GitHub repository link."""
        footer_path = DOCS_ROOT / "_includes/footer.html"
        assert footer_path.exists(), "Missing _includes/footer.html"
        content = footer_path.read_text()
        assert "github.com" in content.lower(), "_includes/footer.html must link to GitHub"


class TestCSSFile:
    """Test that the CSS file exists with required dark theme styles."""

    def test_css_file_exists(self) -> None:
        """docs/assets/css/main.css must exist."""
        css_path = DOCS_ROOT / "assets/css/main.css"
        assert css_path.exists(), f"Missing: {css_path}"

    def test_css_has_dark_background_color(self) -> None:
        """CSS must define the slate-950 dark background color."""
        css_path = DOCS_ROOT / "assets/css/main.css"
        assert css_path.exists(), "Missing assets/css/main.css"
        content = css_path.read_text()
        assert "#020617" in content, "CSS must define background color #020617 (slate-950)"

    def test_css_has_card_surface_color(self) -> None:
        """CSS must define the slate-900 card surface color."""
        css_path = DOCS_ROOT / "assets/css/main.css"
        assert css_path.exists(), "Missing assets/css/main.css"
        content = css_path.read_text()
        assert "#0f172a" in content, "CSS must define card surface color #0f172a (slate-900)"

    def test_css_has_emerald_accent_color(self) -> None:
        """CSS must define the emerald accent color."""
        css_path = DOCS_ROOT / "assets/css/main.css"
        assert css_path.exists(), "Missing assets/css/main.css"
        content = css_path.read_text()
        assert "#10b981" in content, "CSS must define emerald accent color #10b981"

    def test_css_has_jetbrains_mono_font(self) -> None:
        """CSS must reference JetBrains Mono font for code blocks."""
        css_path = DOCS_ROOT / "assets/css/main.css"
        assert css_path.exists(), "Missing assets/css/main.css"
        content = css_path.read_text()
        assert "JetBrains Mono" in content or "JetBrainsMono" in content, "CSS must reference JetBrains Mono font"

    def test_css_has_responsive_styles(self) -> None:
        """CSS must have responsive media queries."""
        css_path = DOCS_ROOT / "assets/css/main.css"
        assert css_path.exists(), "Missing assets/css/main.css"
        content = css_path.read_text()
        assert "@media" in content, "CSS must have responsive media queries"

    def test_css_has_code_block_styles(self) -> None:
        """CSS must have code block/pre element styling."""
        css_path = DOCS_ROOT / "assets/css/main.css"
        assert css_path.exists(), "Missing assets/css/main.css"
        content = css_path.read_text()
        assert "pre" in content and "code" in content, "CSS must style pre and code elements"


class TestDefaultLayoutDarkTheme:
    """Test that the default layout uses the dark theme correctly."""

    def test_layout_references_main_css(self) -> None:
        """default.html must reference the main CSS stylesheet."""
        layout_path = DOCS_ROOT / "_layouts/default.html"
        assert layout_path.exists(), "Missing _layouts/default.html"
        content = layout_path.read_text()
        assert "main.css" in content or "head.html" in content, (
            "default.html must reference main.css (directly or via head.html)"
        )

    def test_layout_has_mobile_nav_support(self) -> None:
        """default.html must include mobile hamburger menu support."""
        layout_path = DOCS_ROOT / "_layouts/default.html"
        assert layout_path.exists(), "Missing _layouts/default.html"
        content = layout_path.read_text()
        # Mobile menu could be implemented via JS or CSS classes
        assert any(
            term in content for term in ["hamburger", "mobile-menu", "menu-toggle", "sidebar-toggle", "nav-toggle"]
        ), "_layouts/default.html must include mobile menu toggle"

    def test_layout_has_edit_on_github_link(self) -> None:
        """default.html must include an 'Edit on GitHub' link."""
        layout_path = DOCS_ROOT / "_layouts/default.html"
        assert layout_path.exists(), "Missing _layouts/default.html"
        content = layout_path.read_text()
        assert "Edit on GitHub" in content or "edit" in content.lower(), (
            "_layouts/default.html must include an 'Edit on GitHub' link"
        )


class TestSEOFiles:
    """Test that SEO support files are present."""

    def test_robots_txt_exists(self) -> None:
        """docs/robots.txt must exist."""
        robots_path = DOCS_ROOT / "robots.txt"
        assert robots_path.exists(), f"Missing: {robots_path}"

    def test_robots_txt_content(self) -> None:
        """docs/robots.txt must allow all crawlers."""
        robots_path = DOCS_ROOT / "robots.txt"
        assert robots_path.exists(), "Missing robots.txt"
        content = robots_path.read_text()
        assert "User-agent" in content, "robots.txt must specify User-agent"
