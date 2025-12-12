print("Flask is starting...")
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt
from MySQLdb.cursors import DictCursor
from flask_mysqldb import MySQLdb
from flask_socketio import SocketIO, join_room, leave_room, emit


app = Flask(__name__)
app.secret_key = 'flirtit_secretkey'  # change this later for better security

# MySQL Config
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Ranffer123!'
app.config['MYSQL_DB'] = 'flirtit_db'

mysql = MySQL(app)
bcrypt = Bcrypt(app)

# Socket.IO
socketio = SocketIO(app, cors_allowed_origins="*")

# ---------------- In-memory data structures ----------------

# Set of allowed chat pairs (stored as sorted tuples → (smaller_id, bigger_id))
allowed_conversations = set()

# Messages per conversation
# key: (user1_id, user2_id)  (sorted tuple)
# value: list of { from_id, text }
conversations_messages = {}


def get_room_id(a, b):
    """Return a stable room key for two users."""
    a = int(a)
    b = int(b)
    return (a, b) if a < b else (b, a)


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
        print(interests)

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

    print("Current user details: ",user)

    return render_template("profile.html", user = user)


# ---- LOGIN ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None   # ← add this

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
            error = "Invalid email or password."

    return render_template('login.html', error=error)
#####################################

@app.route('/like/<int:other_id>', methods=['POST'])
def like_user(other_id):
    user_id = session.get('user_id')
    if not user_id:
        return "Unauthorized", 401

    room = get_room_id(user_id, other_id)
    allowed_conversations.add(room)

    # Make sure a message list exists for this conversation
    if room not in conversations_messages:
        conversations_messages[room] = []

    return '', 204

@app.route('/chat/<int:other_id>')
def chat(other_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    room = get_room_id(user_id, other_id)

    # Enforce: can only chat if someone already liked (swiped right)
    if room not in allowed_conversations:
        flash("You can only message someone after swiping right on them.")
        return redirect(url_for('main'))

    # Get other user's details for display (name, photo)
    cursor = mysql.connection.cursor(DictCursor)
    cursor.execute(
        "SELECT full_name, profile_pic FROM user_details WHERE user_id = %s",
        (other_id,)
    )
    other_user = cursor.fetchone()
    cursor.close()

    messages = conversations_messages.get(room, [])

    return render_template(
        'chat.html',
        other_user=other_user,
        other_id=other_id,
        current_user_id=user_id,
        messages=messages
    )
@socketio.on('join')
def handle_join(data):
    user_id = session.get('user_id')
    if not user_id:
        return

    other_id = int(data.get('other_id'))
    room = get_room_id(user_id, other_id)

    # Only join if conversation is allowed
    if room not in allowed_conversations:
        return

    join_room(room)

    # Send existing messages to the user who just joined
    history = conversations_messages.get(room, [])
    emit('history', history)


@socketio.on('send_message')
def handle_send_message(data):
    user_id = session.get('user_id')
    if not user_id:
        return

    other_id = int(data.get('other_id'))
    text = (data.get('text') or '').strip()
    if not text:
        return

    room = get_room_id(user_id, other_id)
    if room not in allowed_conversations:
        return  # not allowed

    msg = {
        'from_id': int(user_id),
        'text': text
    }

    # Save to in-memory storage
    conversations_messages.setdefault(room, []).append(msg)

    # Broadcast to both participants in the room
    emit('new_message', msg, room=room)



##############################
# ---- MAIN ----
@app.route('/main')
def main():
    user_id = session.get('user_id')
    if not user_id:
        # no one logged in → go to login
        return redirect(url_for('login'))
    
    cursor = mysql.connection.cursor(DictCursor)

    cursor.execute("SELECT gender_interest, interests FROM user_details WHERE user_id = %s", (user_id,))
    user = cursor.fetchone()

    if user is None:
        cursor.close()
        flash("Please complete your details first.")
        return redirect(url_for('details'))  # or whatever route shows the details form

    user_gender_interest = user['gender_interest']
    user_interests = user['interests']
    print("<Current user gender interest> ", user_gender_interest, " <Current user interests> ", user_interests)
    print()
    user_interests_list = [i.strip() for i in user_interests.split(",")]
    print("List of the user interests: ", user_interests_list)
    print()

    if user_gender_interest == "everyone":
        print("Current user gender interests: ", user_gender_interest)
        print()

        cursor.execute("SELECT id, user_id, full_name, age, interests, gender, gender_interest, profile_pic FROM user_details WHERE user_id != %s",(user_id,))
        possible_matches = cursor.fetchall()
        print("Display all: ",possible_matches)
        print()

        cursor.execute("SELECT user_id FROM user_details WHERE user_id = %s",(user_id,))
        current_user_id = cursor.fetchall()
        print("Current user: ", current_user_id)

        results = []
        for u in possible_matches:
            print()
            print("The for loop: ",u)
            match_interests_list = [i.strip() for i in u['interests'].split(",")]
            print("Match interestslist", match_interests_list)

            shared_interests_count = len(set(user_interests_list) & set(match_interests_list))
            print("Count of shared interests :", shared_interests_count)

            
            percentage = (shared_interests_count / len(user_interests_list)) * 100 if shared_interests_count > 0 else 0
            
            results.append({
                "user_same_interests": u,
                "count": shared_interests_count,
                "percentage": round(percentage, 2)
            })
            print("The Percentage :", percentage)

        print()
        print("The resulta list :", results,)

        print()

        #Sort highest to lowest percentage
        results = sorted(results, key=lambda x: x['percentage'], reverse=True)
        print("Sorted users who have common interests: ", results)

################################################################

        # --- GET ALL POSSIBLE MATCHES ---
    else:
        cursor.execute("SELECT id, user_id, full_name, age, interests, gender, gender_interest, profile_pic FROM user_details WHERE gender = %s AND user_id != %s", (user_gender_interest, user_id))
        possible_matches = cursor.fetchall()
        print()
        print("Possible matches: ", possible_matches)
        print()

        results = []
        for u in possible_matches:
            print()
            print("The for loop: ",u)
            match_interests_list = [i.strip() for i in u['interests'].split(",")]
            print("Match interestslist", match_interests_list)

            shared_interests_count = len(set(user_interests_list) & set(match_interests_list))
            print("Count of shared interests :", shared_interests_count)

            
            percentage = (shared_interests_count / len(user_interests_list)) * 100 if shared_interests_count > 0 else 0
            
            results.append({
                "user_same_interests": u,
                "count": shared_interests_count,
                "percentage": round(percentage, 2)
            })
            print("The Percentage :", percentage)

        print()
        print("The resulta list :", results)

        print()

        #Sort highest to lowest percentage
        results = sorted(results, key=lambda x: x['percentage'], reverse=True)
        print("Sorted users who have common interests: ", results)

    cursor.close()

    print("IM INNNNNN")

    return render_template("main.html", match_interest=results, current_user_id=user_id)
    
# ---- CONTACT ----
@app.route('/contact')
def contact():
    return render_template('contact.html')

# ---- ABOUT ----
@app.route('/about')
def about():
    return render_template('about.html')

# ---- LOGOUT ----
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.")
    return redirect(url_for('login'))

# ----- RUN APP ------
if __name__ == '__main__':
    socketio.run(app, debug=True)