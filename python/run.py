from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(port=9093, debug=True)
