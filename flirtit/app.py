print("Flask is starting...")
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt
from MySQLdb.cursors import DictCursor

app = Flask(__name__)
app.secret_key = 'flirtit_secretkey'  # change this later for better security

# MySQL Config 
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '2005'   
app.config['MYSQL_DB'] = 'flirtit_db'

mysql = MySQL(app)
bcrypt = Bcrypt(app)

# ========== ROUTES ==========
@app.route('/')
def home():
    return redirect(url_for('login'))

# ---- REGISTER ----
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        confirm = request.form['confirm']

        if password != confirm:
            flash("Passwords do not match!")
            return redirect(url_for('register'))

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s", [email])
        existing_user = cur.fetchone()

        if existing_user:
            flash("Email already registered!")
            return redirect(url_for('register'))

        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        cur.execute("INSERT INTO users (email, password) VALUES (%s, %s)", (email, hashed_pw))
        mysql.connection.commit()

        # Fetch the new user's ID
        cur = mysql.connection.cursor()
        cur.execute("SELECT id FROM users WHERE email = %s", [email])
        user = cur.fetchone()
        session['user_id'] = user[0]
        cur.close()

       # flash("Account created successfully! Please complete your details.")
        return redirect(url_for('details'))

    return render_template('register.html')

# ---- DETAILS ----
import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/details', methods=['GET', 'POST'])
def details():
    if request.method == 'POST':
        user_id = session.get('user_id')  # get logged-in user ID

        if not user_id:
            flash("Session expired. Please log in again.")
            return redirect(url_for('login'))
        
        #required dapat/ must not nulll. para dili ma error  and profile page ####################################

        fullname        = request.form.get('fullName')
        age             = request.form.get('age')
        gender          = request.form.get('gender')
        gender_interest = request.form.get('genderInterest')
        interests = ', '.join(request.form.getlist('interests[]'))
        ########################################################

        # Handle file upload
        file        = request.files.get('profilePic')
        profile_pic = None
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            profile_pic = filename
        

        # Save to DB
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO user_details 
            (user_id, full_name, age, gender, gender_interest, interests, profile_pic)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (user_id, fullname, age, gender, gender_interest, interests, profile_pic))
        mysql.connection.commit()
        cur.close()


        return redirect(url_for('login'))   

    return render_template('details.html')

# ---- PROFILE ----
@app.route('/profile')
def profile():
    user_id = session.get('user_id')

    #cur = mysql.connection.cursor()
    #cur.execute("SELECT id, user_id, full_name, age, gender, gender_interest, interests, profile_pic FROM user_details WHERE user_id = %s" , (user_id,) )
                
    #user_details = cur.fetchone()
    #cur.close()

    #print("Details try", user_details[2])

    #####################################################################

    cursor = mysql.connection.cursor(DictCursor)
    cursor.execute("SELECT id, user_id, full_name, age, gender, gender_interest, interests, profile_pic FROM user_details WHERE user_id = %s" , (user_id,) )
    user = cursor.fetchone()
    cursor.close()

    print(user)

    return render_template("profile.html", user = user)


# ---- LOGIN ----
@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s", [email])
        user = cur.fetchone()
        cur.close()

        if user and bcrypt.check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['email'] = user[1]
            return redirect(url_for('main'))
        else:
            flash("Invalid credentials!")
            return redirect(url_for('login'))

    return render_template('login.html')

# ---- MAIN ----
@app.route('/main')
def main():
    if 'user_id' in session:
        return render_template('main.html')
    else:
        return redirect(url_for('login'))

# ---- LOGOUT ----
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.")
    return redirect(url_for('login'))

# ----- RUN APP ------
if __name__ == '__main__':
    app.run(debug=True)