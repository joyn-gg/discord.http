from sphinx.errors import ExtensionError


def add_js(app, pagename, template_name, context, doctree):
    if not app.config.ga_enabled:
        return

    meta = context.get("metatags", "")

    meta += """
    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=%s"></script>
    """ % app.config.ga_id

    meta += """
    <script>
        window.dataLayer = window.dataLayer || [];
        function gtag(){dataLayer.push(arguments);}
        gtag('js', new Date());
        gtag('config', '%s');
    </script>
    """ % app.config.ga_id

    context["metatags"] = meta


def check_config(app):
    if not app.config.ga_id:
        raise ExtensionError("ga_id config value must be set")


def setup(app):
    app.add_config_value("ga_enabled", False, "html")
    app.add_config_value("ga_id", "", "html")
    app.connect("html-page-context", add_js)
    app.connect("builder-inited", check_config)

    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
