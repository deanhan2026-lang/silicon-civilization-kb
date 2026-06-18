import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from anti_drift.db import init_db, get_db
from anti_drift.models import User
from anti_drift.auth import hash_password, verify_password

init_db()
u = User(email='test@test.com', hashed_password=hash_password('test123'))
db = next(get_db())
db.add(u)
db.commit()
print(f'User created: id={u.id}')
print(f'Verify: {verify_password("test123", u.hashed_password)}')
db.close()
