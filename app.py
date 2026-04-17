from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file, abort
from datetime import datetime, timedelta
import json, os, re, qrcode, io, smtplib, shutil
from email.message import EmailMessage

BASE = os.path.dirname(__file__)

def is_writable(path):
    try:
        test_file = os.path.join(path, '.write_test')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        return True
    except Exception:
        return False

if not is_writable(BASE):
    DATA_DIR = "/tmp/data"
    QRC_DIR = "/tmp/qrcodes"
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(QRC_DIR, exist_ok=True)
    # Copy existing files from project tree to /tmp if not already there
    for filename in ["users.json", "books.json", "config.json"]:
        src = os.path.join(BASE, "data", filename)
        dst = os.path.join(DATA_DIR, filename)
        if not os.path.exists(dst) and os.path.exists(src):
            # Manually read and write to avoid copying read-only permissions from Vercel's source tree
            with open(src, 'r', encoding='utf-8') as fr:
                content = fr.read()
            with open(dst, 'w', encoding='utf-8') as fw:
                fw.write(content)
else:
    DATA_DIR = os.path.join(BASE, "data")
    QRC_DIR = os.path.join(BASE, "static", "qrcodes")

USERS_FILE = os.path.join(DATA_DIR, "users.json")
BOOKS_FILE = os.path.join(DATA_DIR, "books.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

def ensure():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(QRC_DIR, exist_ok=True)
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE,"w") as f:
            json.dump({"admin":{"password":"admin","role":"admin","borrowed":[],"fine":0,"history":[],"total_borrowed":0}}, f, indent=2)
    if not os.path.exists(BOOKS_FILE):
        with open(BOOKS_FILE,"w") as f:
            json.dump({}, f, indent=2)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE,"w") as f:
            json.dump({"smtp":{"host":"","port":587,"username":"","password":"","from_email":"noreply@library.example"}}, f, indent=2)

ensure()

app = Flask(__name__)
app.secret_key = "replace-with-secure-key"

def load_users():
    with open(USERS_FILE) as f: return json.load(f)
def save_users(u):
    with open(USERS_FILE,"w") as f: json.dump(u,f,indent=2)
def load_books():
    with open(BOOKS_FILE) as f: return json.load(f)
def save_books(b):
    with open(BOOKS_FILE,"w") as f: json.dump(b,f,indent=2)
def load_config():
    with open(CONFIG_FILE) as f: return json.load(f)

# validators
EMAIL_RE = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w{2,}$")
PWD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$")

@app.template_filter('datefmt')
def _fmt(d):
    try:
        return datetime.fromisoformat(d).strftime('%Y-%m-%d')
    except:
        return d

@app.route('/')
def index():
    books = load_books()
    return render_template('index.html', books=books)

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method=='POST':
        username = request.form['username'].strip()
        password = request.form['password']
        role = request.form.get('role','user')
        if not EMAIL_RE.match(username):
            flash('Registration requires a valid email address as username.','danger')
            return redirect(url_for('register'))
        if not PWD_RE.match(password):
            flash('Password must be ≥8 chars, include upper, lower, digit and special char.','danger')
            return redirect(url_for('register'))
        users = load_users()
        if username in users:
            flash('Username already exists.','danger'); return redirect(url_for('register'))
        users[username] = {'password':password,'role':role,'borrowed':[],'fine':0,'history':[],'total_borrowed':0}
        save_users(users)
        flash('Registered. Please login.','success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        username = request.form['username'].strip()
        password = request.form['password']
        users = load_users()
        u = users.get(username)
        if u and u['password']==password:
            session['username']=username; flash('Welcome!','success'); return redirect(url_for('dashboard'))
        flash('Invalid credentials.','danger'); return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username',None); flash('Logged out.','info'); return redirect(url_for('index'))

def current_user():
    un = session.get('username'); 
    if not un: return None, None
    users = load_users(); return un, users.get(un)

@app.route('/dashboard')
def dashboard():
    un, u = current_user()
    if not un: return redirect(url_for('login'))
    books = load_books()
    # compute borrowed info and recommendations
    borrowed = []
    for item in u.get('borrowed',[]):
        try: due = datetime.fromisoformat(item['due'])
        except: due = datetime.now()
        days_left = (due - datetime.now()).days
        borrowed.append({'title':item['title'],'due':due.isoformat(),'days_left':days_left})
    # recommend based on history genres
    genre_count = {}
    for h in u.get('history',[]):
        b = books.get(h)
        if b: genre_count[b.get('genre','')]=genre_count.get(b.get('genre',''),0)+1
    top_genres = sorted(genre_count.items(), key=lambda x:-x[1])[:2]
    recs = []
    if top_genres:
        favored = top_genres[0][0]
        for title,info in books.items():
            if info.get('genre')==favored and info.get('copies',0)>0:
                recs.append({'title':title,'author':info.get('author')})
    # simple leaderboard
    users = load_users()
    leaderboard = sorted([(name,info.get('total_borrowed',0)) for name,info in users.items()], key=lambda x:-x[1])[:5]
    return render_template('dashboard.html', username=un, user=u, books=books, borrowed=borrowed, recs=recs, leaderboard=leaderboard)

@app.route('/add_book', methods=['POST'])
def add_book():
    un, u = current_user()
    if not u or u.get('role')!='admin': flash('Admin required','danger'); return redirect(url_for('login'))
    title = request.form['title'].strip(); copies = int(request.form.get('copies',1))
    author = request.form.get('author','Unknown').strip(); genre = request.form.get('genre','General').strip()
    books = load_books()
    if title in books:
        books[title]['copies'] = books[title].get('copies',0) + copies
    else:
        books[title] = {'copies':copies,'author':author,'genre':genre,'qr': title[:20].replace(' ','_') + str(len(books))}
    save_books(books)
    flash('Book added.','success'); return redirect(url_for('dashboard'))

@app.route('/borrow', methods=['POST'])
def borrow():
    un, u = current_user()
    if not u: flash('Login required','danger'); return redirect(url_for('login'))
    if u.get('fine',0)>0: flash(f'Unpaid fine ₹{u.get("fine")}', 'warning'); return redirect(url_for('dashboard'))
    title = request.form['title'].strip(); books = load_books()
    if title not in books: flash('Book not found','danger'); return redirect(url_for('dashboard'))
    if books[title].get('copies',0)<=0: flash('Out of stock','danger'); return redirect(url_for('dashboard'))
    books[title]['copies'] -= 1; save_books(books)
    due = (datetime.now() + timedelta(days=7)).isoformat()
    users = load_users(); users[un]['borrowed'].append({'title':title,'due':due}); users[un]['history'].append(title); users[un]['total_borrowed'] = users[un].get('total_borrowed',0)+1
    save_users(users)
    flash(f'Borrowed {title}. Due {due[:10]}','success'); return redirect(url_for('dashboard'))

@app.route('/return', methods=['POST'])
def return_book():
    un, u = current_user()
    if not u: flash('Login required','danger'); return redirect(url_for('login'))
    title = request.form['title'].strip(); users = load_users(); borrowed = users[un]['borrowed']
    for item in borrowed:
        if item['title']==title:
            borrowed.remove(item)
            books = load_books(); books[title]['copies'] = books.get(title,{}).get('copies',0)+1; save_books(books)
            now = datetime.now(); due_dt = datetime.fromisoformat(item['due'])
            if now>due_dt:
                days = (now-due_dt).days; fine = days*10; users[un]['fine'] = users[un].get('fine',0)+fine; save_users(users)
                flash(f'Returned late by {days} days. Fine ₹{fine}','warning')
            else:
                save_users(users); flash('Returned on time','success')
            return redirect(url_for('dashboard'))
    flash('Book not borrowed by you','danger'); return redirect(url_for('dashboard'))

@app.route('/pay_fine', methods=['POST'])
def pay_fine():
    un, u = current_user(); users = load_users()
    if users[un].get('fine',0)==0: flash('No fine','info')
    else:
        amt = users[un]['fine']; users[un]['fine']=0; save_users(users); flash(f'Paid ₹{amt}','success')
    return redirect(url_for('dashboard'))

@app.route('/users')
def users_page():
    un, u = current_user()
    if not u or u.get('role')!='admin': flash('Admin required','danger'); return redirect(url_for('login'))
    users = load_users(); return render_template('users.html', users=users)

@app.route('/search')
def search():
    q = request.args.get('q','').lower(); author = request.args.get('author','').lower(); genre = request.args.get('genre','').lower()
    books = load_books(); results = {}
    for title,info in books.items():
        if q and q not in title.lower(): continue
        if author and author not in info.get('author','').lower(): continue
        if genre and genre not in info.get('genre','').lower(): continue
        results[title] = info.get('copies',0)
    return jsonify(results)

@app.route('/qrcode/<book>')
def qrcode_image(book):
    books = load_books()
    if book not in books: abort(404)
    qr_text = books[book].get('qr',book)
    img = qrcode.make(qr_text)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

# manual reminders (admin triggered)
def send_email(to, subject, body):
    cfg = load_config()
    smtp = cfg.get('smtp',{})
    host = smtp.get('host')
    if not host:
        print(f"SIMULATED EMAIL -> To: {to} Subject: {subject}\n{body}\n---\n")
        return True, 'simulated'
    try:
        msg = EmailMessage(); msg['From'] = smtp.get('from_email'); msg['To']=to; msg['Subject']=subject; msg.set_content(body)
        with smtplib.SMTP(smtp.get('host'), smtp.get('port')) as s:
            s.starttls(); s.login(smtp.get('username'), smtp.get('password')); s.send_message(msg)
        return True, 'sent'
    except Exception as e:
        print('Email failed:',e); return False, str(e)

@app.route('/send_reminders')
def send_reminders():
    un, u = current_user(); 
    if not u or u.get('role')!='admin': flash('Admin required','danger'); return redirect(url_for('login'))
    users = load_users(); count=0; failures=[]
    for name,info in users.items():
        for item in info.get('borrowed',[]):
            due = datetime.fromisoformat(item['due']); days_left = (due - datetime.now()).days
            if days_left<=2:
                to = name
                subject = f"Reminder: '{item['title']}' due in {days_left} days"
                body = f"Dear {name},\n\nYour borrowed book '{item['title']}' is due on {due.date()}. Please return on time to avoid fines.\n\nThanks, Library"
                ok, msg = send_email(to, subject, body)
                if ok: count+=1
                else: failures.append((name,msg))
    flash(f'Reminders processed: {count}. Failures: {len(failures)}','info'); return redirect(url_for('dashboard'))

# lightweight AI chatbot (keyword based)
@app.route('/chat', methods=['POST'])
def chat():
    q = request.form.get('q','').lower(); books = load_books()
    # keyword matching
    if 'recommend' in q or 'suggest' in q:
        # suggest popular available books
        avail = sorted([(t,i.get('copies',0)) for t,i in books.items() if i.get('copies',0)>0], key=lambda x:-x[1])[:5]
        resp = 'Top available: ' + ', '.join([a[0] for a in avail])
    elif 'genre' in q:
        # attempt extract genre
        words = q.split()
        for g in set([i.get('genre','').lower() for i in books.values()]):
            if g and g in q: 
                resp = 'Books in '+g+': ' + ', '.join([t for t,i in books.items() if i.get('genre','').lower()==g])
                break
        else:
            resp = 'Try asking like "recommend science fiction" or mention a genre.'
    else:
        resp = 'Sorry, I can suggest books. Try "recommend" or "suggest [genre]".'
    return jsonify({'reply':resp})

if __name__=='__main__':
    app.run(debug=True)
