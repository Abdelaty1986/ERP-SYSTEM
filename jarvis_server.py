from flask import Flask

from jarvis_app import create_jarvis_blueprint


def create_app():
    app = Flask(__name__)
    app.register_blueprint(create_jarvis_blueprint())
    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=False)
