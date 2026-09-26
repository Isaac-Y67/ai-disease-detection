from flask import Flask #imports the Flask class from the library we just installed

app = Flask(__name__) #creates your actual web application object. __name__ tells Flask where this file lives, so it knows where to look for other resources (templates, static files) later

@app.route("/") #this is a decorator — it tells Flask "when someone visits the root URL (/), run the function directly below me"
#the function that runs on that visit; whatever it returns becomes what the browser displays
def home():
    return "AI Disease Detection System — backend is running."

#his block only runs when you execute this file directly (not when it's imported elsewhere later). debug=True turns on auto-reload (saves you restarting the server every time you edit code) and shows detailed error pages if something breaks
if __name__ == "__main__":
    app.run(debug=True)