from flask import Flask, render_template, url_for

app = Flask(__name__)

@app.route('/')
def home():
    return 'Hello from Flask on Vercel!'

@app.route('/about')
def about():
    return render_template('bio.html', url_for=url_for)

if __name__ == '__main__':
    app.run('localhost', port=3000, debug=True)