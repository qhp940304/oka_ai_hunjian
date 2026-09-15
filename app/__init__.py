from app.config import Config


def create_app(init_database: bool = True):
    from flask import Flask

    app = Flask(
        __name__,
        static_folder="../static",
        static_url_path="/static",
        template_folder="../templates",
    )
    app.config.from_object(Config)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["PERMANENT_SESSION_LIFETIME"] = 86400 * 14
    app.config["MAX_CONTENT_LENGTH"] = Config.MAX_CONTENT_LENGTH

    if init_database:
        from app.schema import init_db

        init_db()

    from app.routes.auth import bp as auth_bp
    from app.routes.download import bp as download_bp
    from app.routes.pages import bp as pages_bp
    from app.routes.tasks import bp as tasks_bp
    from app.routes.upload import bp as upload_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(download_bp)
    app.register_blueprint(upload_bp)

    @app.get("/api/v1/health")
    def api_health():
        from flask import jsonify

        return jsonify(ok=True, service="oka-consumer")

    return app
