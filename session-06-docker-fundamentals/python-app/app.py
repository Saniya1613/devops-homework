from flask import Flask

app = Flask(__name__)

@app.route("/")
def hello():
    return "<h1>Hello World from Python (Flask) in Docker!</h1><p>Saniya Sanjiv Patil - 24bcs10246</p>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
