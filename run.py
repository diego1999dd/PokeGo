from app import create_app

app = create_app()

if __name__ == '__main__':
    # Rodar em modo debug para desenvolvimento
    app.run(debug=True)