import os, hashlib, secrets, smtplib, logging
from email.message import EmailMessage
from datetime import date, datetime, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("borrowback")
app = FastAPI(title="BorrowBack Firebase API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

def init_firestore():
    import os
    import firebase_admin
    from firebase_admin import credentials, firestore

    if not firebase_admin._apps:
        key_path = os.getenv(
            "FIREBASE_SERVICE_ACCOUNT",
            "serviceAccountKey.json"
        )

        project_id = os.getenv("FIREBASE_PROJECT_ID")

        cred = credentials.Certificate(key_path)

        firebase_admin.initialize_app(
            cred,
            {"projectId": project_id}
        )

    return firestore.client()
db = None
@app.on_event("startup")
def startup():
    global db
    db = init_firestore()

def now():
    return datetime.now().astimezone().isoformat()

def serialize(value):
    if isinstance(value, datetime): return value.isoformat()
    if isinstance(value, date): return value.isoformat()
    if isinstance(value, dict): return {k: serialize(v) for k,v in value.items()}
    if isinstance(value, list): return [serialize(v) for v in value]
    return value

def next_id(collection):
    ref = db.collection("_counters").document(collection)
    @firestore.transactional
    def increment(transaction):
        snap = ref.get(transaction=transaction)
        value = (snap.to_dict() or {}).get("value", 0) + 1
        transaction.set(ref, {"value": value})
        return value
    return increment(db.transaction())

def get_doc(collection, doc_id):
    snap = db.collection(collection).document(str(doc_id)).get()
    if not snap.exists: return None
    d = snap.to_dict() or {}
    d.setdefault("id", str(doc_id))
    return serialize(d)

def all_docs(collection):
    return [serialize({**(s.to_dict() or {}), "id": s.id}) for s in db.collection(collection).stream()]

def save(collection, doc_id, data):
    db.collection(collection).document(str(doc_id)).set(data)
def patch(collection, doc_id, data):
    db.collection(collection).document(str(doc_id)).update(data)

def send_email(to_email, subject, body):
    if not to_email or not os.getenv("SMTP_HOST") or not os.getenv("SMTP_FROM"): return False
    try:
        msg=EmailMessage(); msg["Subject"]=subject; msg["From"]=os.getenv("SMTP_FROM"); msg["To"]=to_email; msg.set_content(body)
        host=os.getenv("SMTP_HOST"); port=int(os.getenv("SMTP_PORT","587"))
        if os.getenv("SMTP_USE_SSL","false").lower()=="true":
            with smtplib.SMTP_SSL(host,port,timeout=12) as s:
                if os.getenv("SMTP_USER"): s.login(os.getenv("SMTP_USER"),os.getenv("SMTP_PASSWORD","").replace(" ",""))
                s.send_message(msg)
        else:
            with smtplib.SMTP(host,port,timeout=12) as s:
                if os.getenv("SMTP_USE_TLS","true").lower()=="true": s.starttls()
                if os.getenv("SMTP_USER"): s.login(os.getenv("SMTP_USER"),os.getenv("SMTP_PASSWORD","").replace(" ",""))
                s.send_message(msg)
        return True
    except Exception as e:
        logger.warning("Email send failed: %s", e); return False

def notify_user(user_id, event_type, title, message, email_subject=None, email_body=None):
    if not user_id: return
    notification_id=str(next_id("notifications"))
    save("notifications", notification_id, {"id":notification_id,"user_id":str(user_id),"event_type":event_type,"title":title,"message":message,"is_read":False,"created_at":now()})
    user=get_doc("users",user_id)
    if user and email_subject and email_body: send_email(user.get("email"),email_subject,email_body)

def current_user(user_id):
    if not user_id: raise HTTPException(401,"Missing X-User-Id header")
    user=get_doc("users",user_id)
    if not user: raise HTTPException(401,"Unknown user. Please register again.")
    return user

class RegisterIn(BaseModel):
    display_name:str=Field(min_length=2,max_length=100)
    email:str=Field(min_length=5,max_length=190)
    password:str=Field(min_length=6,max_length=128)
    branch:str=""
    section:str=""
    contact:str=""
class LoginIn(BaseModel):
    email:str
    password:str
class ItemIn(BaseModel):
    title:str=Field(min_length=2,max_length=120)
    category:str=Field(min_length=2,max_length=60)
    description:str=""
class RequestIn(BaseModel):
    item_id:Optional[int]=None
    due_date:Optional[date]=None
    requested_title:Optional[str]=None
    requested_category:str="General"
    requested_description:str=""
class ProfileUpdateIn(BaseModel):
    display_name:str=Field(min_length=2,max_length=100)
    email:str=Field(min_length=5,max_length=190)
    branch:str=""
    section:str=""
    contact:str=""
class RatingIn(BaseModel):
    rated_user_id:str
    request_id:int
    rating:int=Field(ge=1,le=5)
    comment:str=Field(default="",max_length=500)

def password_hash(password,salt=None):
    salt=salt or secrets.token_hex(16)
    return f"{salt}${hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),200000).hex()}"
def verify_password(password,stored):
    try:
        salt,digest=stored.split("$",1)
        return secrets.compare_digest(password_hash(password,salt).split("$",1)[1],digest)
    except Exception:return False

@app.get("/")
def root(): return {"app":"BorrowBack Firebase API","docs":"/docs","status":"ok","database":"Firebase Cloud Firestore"}

@app.post("/api/auth/register",status_code=201)
def register(payload:RegisterIn):
    email=payload.email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]: raise HTTPException(400,"Enter a valid email address")
    if any(u.get("email","").lower()==email for u in all_docs("users")): raise HTTPException(409,"An account with this email already exists")
    uid="u_"+secrets.token_hex(12)
    user={"id":uid,"display_name":payload.display_name.strip(),"email":email,"password_hash":password_hash(payload.password),"branch":payload.branch.strip(),"section":payload.section.strip(),"contact":payload.contact.strip(),"created_at":now()}
    save("users",uid,user)
    return {k:v for k,v in user.items() if k!="password_hash"}

@app.post("/api/auth/login")
def login(payload:LoginIn):
    email=payload.email.strip().lower()
    users=[u for u in all_docs("users") if u.get("email","").lower()==email]
    if not users or not users[0].get("password_hash") or not verify_password(payload.password,users[0]["password_hash"]): raise HTTPException(401,"Invalid email or password")
    return {k:v for k,v in users[0].items() if k!="password_hash"}

@app.get("/api/users/me")
def me(x_user_id:Optional[str]=Header(default=None)):
    user=current_user(x_user_id)
    reqs=[r for r in all_docs("borrow_requests") if r.get("borrower_id")==user["id"]]
    completed=sum(1 for r in reqs if r.get("status")=="returned")
    today=date.today().isoformat()
    late=sum(1 for r in reqs if (r.get("status")=="returned" and r.get("returned_at") and r.get("due_date") and r["returned_at"][:10]>r["due_date"][:10]) or (r.get("status") in ("approved","overdue") and r.get("due_date") and r["due_date"][:10]<today))
    ratings=[r for r in all_docs("user_ratings") if r.get("rated_user_id")==user["id"]]
    avg=sum(r["rating"] for r in ratings)/len(ratings) if ratings else 0
    return {k:v for k,v in user.items() if k!="password_hash"} | {"completed_borrows":completed,"late_returns":late,"trust_score":max(0,100-late*15),"average_rating":avg,"rating_count":len(ratings)}

@app.put("/api/users/me")
def update_profile(payload:ProfileUpdateIn,x_user_id:Optional[str]=Header(default=None)):
    user=current_user(x_user_id); email=payload.email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]: raise HTTPException(400,"Enter a valid email address")
    if any(u["id"]!=user["id"] and u.get("email","").lower()==email for u in all_docs("users")): raise HTTPException(409,"That email address is already used by another account")
    patch("users",user["id"],{"display_name":payload.display_name.strip(),"email":email,"branch":payload.branch.strip(),"section":payload.section.strip(),"contact":payload.contact.strip()})
    return {"message":"Profile updated successfully"}

@app.get("/api/notifications")
def list_notifications(x_user_id:Optional[str]=Header(default=None)):
    user=current_user(x_user_id)
    ns=[n for n in all_docs("notifications") if n.get("user_id")==user["id"]]
    return sorted(ns,key=lambda n:n.get("created_at",""),reverse=True)[:100]

@app.post("/api/notifications/read-all")
def read_all(x_user_id:Optional[str]=Header(default=None)):
    user=current_user(x_user_id)
    for n in all_docs("notifications"):
        if n.get("user_id")==user["id"] and not n.get("is_read"): patch("notifications",n["id"],{"is_read":True})
    return {"message":"Notifications marked as read"}

@app.get("/api/items")
def list_items(available_only:bool=True):
    users={u["id"]:u for u in all_docs("users")}
    items=[]
    for i in all_docs("items"):
        if available_only and not i.get("available",True): continue
        owner=users.get(i.get("owner_id"),{})
        items.append(i|{"owner_name":owner.get("display_name"),"owner_branch":owner.get("branch"),"owner_section":owner.get("section"),"owner_contact":owner.get("contact"),"owner_email":owner.get("email")})
    return sorted(items,key=lambda i:i.get("created_at",""),reverse=True)

@app.post("/api/items",status_code=201)
def add_item(payload:ItemIn,x_user_id:Optional[str]=Header(default=None)):
    user=current_user(x_user_id); iid=next_id("items")
    save("items",str(iid),{"id":iid,"owner_id":user["id"],"title":payload.title.strip(),"category":payload.category.strip(),"description":payload.description.strip(),"available":True,"created_at":now()})
    return {"id":iid,"message":"Item listed successfully"}

@app.post("/api/requests",status_code=201)
def create_request(payload:RequestIn,x_user_id:Optional[str]=Header(default=None)):
    user=current_user(x_user_id); item=None
    if payload.item_id is not None:
        item=get_doc("items",payload.item_id)
        if not item: raise HTTPException(404,"Item not found")
        if item["owner_id"]==user["id"]: raise HTTPException(400,"You cannot borrow your own item")
        if not item.get("available",True): raise HTTPException(409,"This item is not available")
        owner_id=item["owner_id"]; title=item["title"]; category=item["category"]
    else:
        title=(payload.requested_title or "").strip(); category=payload.requested_category.strip() or "General"; owner_id=None
        if len(title)<2: raise HTTPException(400,"For an unlisted item, provide requested_title")
    if payload.due_date and payload.due_date<date.today(): raise HTTPException(400,"Due date cannot be in the past")
    rid=next_id("borrow_requests")
    req={"id":rid,"item_id":payload.item_id,"borrower_id":user["id"],"owner_id":owner_id,"due_date":payload.due_date.isoformat() if payload.due_date else None,"status":"pending","requested_item_title":title if item is None else None,"requested_category":category if item is None else None,"requested_description":payload.requested_description.strip(),"requested_at":now(),"approved_at":None,"returned_at":None}
    save("borrow_requests",str(rid),req)
    if owner_id:
        notify_user(owner_id,"borrow_request","New borrow request",f"{user['display_name']} requested to borrow '{title}'. Open BorrowBack to review the request.",f"BorrowBack: new request for {title}",f"{user['display_name']} requested '{title}'. Please sign in to review.")
    else:
        for other in all_docs("users"):
            if other["id"]!=user["id"]:
                notify_user(other["id"],"community_request","New community item request",f"{user['display_name']} is looking for '{title}'. Open BorrowBack to respond.")
    return {"id":rid,"message":"Item request sent" if item is None else "Borrow request sent"}

@app.get("/api/requests")
def list_requests(scope:str="incoming",x_user_id:Optional[str]=Header(default=None)):
    user=current_user(x_user_id)
    if scope not in ("incoming","outgoing","all"): raise HTTPException(400,"scope must be incoming, outgoing, or all")
    users={u["id"]:u for u in all_docs("users")}; items={str(i["id"]):i for i in all_docs("items")}
    result=[]
    for r in all_docs("borrow_requests"):
        owner=r.get("owner_id"); borrower=r.get("borrower_id")
        include=(scope=="incoming" and (owner==user["id"] or owner is None)) or (scope=="outgoing" and borrower==user["id"]) or (scope=="all" and (owner==user["id"] or borrower==user["id"] or owner is None))
        if not include: continue
        bu=users.get(borrower,{}); ou=users.get(owner,{})
        item=items.get(str(r.get("item_id")),{})
        title=item.get("title") or r.get("requested_item_title"); category=item.get("category") or r.get("requested_category")
        result.append(r|{"borrower_name":bu.get("display_name"),"borrower_branch":bu.get("branch"),"borrower_section":bu.get("section"),"borrower_contact":bu.get("contact"),"borrower_email":bu.get("email"),"owner_name":ou.get("display_name"),"owner_branch":ou.get("branch"),"owner_section":ou.get("section"),"owner_contact":ou.get("contact"),"owner_email":ou.get("email"),"title":title,"category":category})
    return sorted(result,key=lambda r:r.get("requested_at",""),reverse=True)

@app.post("/api/requests/{request_id}/decision")
def decide(request_id:str,decision:str,days:int=3,x_user_id:Optional[str]=Header(default=None)):
    user=current_user(x_user_id); req=get_doc("borrow_requests",request_id)
    if not req: raise HTTPException(404,"Request not found")
    if decision not in ("approved","rejected"): raise HTTPException(400,"decision must be approved or rejected")
    if req.get("owner_id") and req["owner_id"]!=user["id"]: raise HTTPException(403,"Only the item owner can decide")
    if req.get("status")!="pending": raise HTTPException(409,"Only pending requests can be decided")
    if decision=="approved":
        if days<1 or days>180: raise HTTPException(400,"Borrowing period must be between 1 and 180 days")
        item_id=req.get("item_id")
        if item_id is None:
            item_id=next_id("items")
            save("items",str(item_id),{"id":item_id,"owner_id":user["id"],"title":req.get("requested_item_title"),"category":req.get("requested_category") or "General","description":req.get("requested_description") or "Requested item","available":True,"created_at":now()})
        item=get_doc("items",item_id)
        if not item or not item.get("available",True): raise HTTPException(409,"Item is already borrowed")
        patch("items",item_id,{"available":False})
        patch("borrow_requests",request_id,{"owner_id":user["id"],"item_id":item_id,"status":"approved","approved_at":now(),"due_date":(date.today()+timedelta(days=days)).isoformat()})
        req.update({"owner_id":user["id"],"item_id":item_id,"status":"approved","due_date":(date.today()+timedelta(days=days)).isoformat()})
    else:
        patch("borrow_requests",request_id,{"owner_id":user["id"],"status":"rejected"}); req.update({"owner_id":user["id"],"status":"rejected"})
    borrower=get_doc("users",req["borrower_id"]); title=(get_doc("items",req.get("item_id")) or {}).get("title") or req.get("requested_item_title") or "item"
    label=decision
    notify_user(req["borrower_id"],f"request_{label}",f"Borrow request {label}",f"Your request for '{title}' was {label} by {user['display_name']}",f"BorrowBack: request {label}",f"Your request for '{title}' was {label} by {user['display_name']}.")
    return {"message":f"Request {decision}"}

@app.post("/api/requests/{request_id}/return")
def confirm_return(request_id:str,x_user_id:Optional[str]=Header(default=None)):
    user=current_user(x_user_id); req=get_doc("borrow_requests",request_id)
    if not req: raise HTTPException(404,"Request not found")
    if req.get("owner_id")!=user["id"]: raise HTTPException(403,"Only the item owner can confirm return")
    if req.get("status") not in ("approved","overdue"): raise HTTPException(409,"Only active borrowings can be returned")
    returned=now(); patch("borrow_requests",request_id,{"status":"returned","returned_at":returned})
    if req.get("item_id") is not None: patch("items",req["item_id"],{"available":True})
    borrower=get_doc("users",req["borrower_id"]); title=(get_doc("items",req.get("item_id")) or {}).get("title") or req.get("requested_item_title") or "item"
    notify_user(req["borrower_id"],"item_returned","Item return confirmed",f"The return of '{title}' has been confirmed by {user['display_name']}.")
    notify_user(user["id"],"item_returned","Item return confirmed",f"'{title}' has been marked as returned. The item is available again.")
    return {"message":"Return confirmed. Item is available again."}

@app.post("/api/requests/{request_id}/overdue")
def mark_overdue(request_id:str,x_user_id:Optional[str]=Header(default=None)):
    user=current_user(x_user_id); req=get_doc("borrow_requests",request_id)
    if not req: raise HTTPException(404,"Borrow request not found")
    if req.get("owner_id")!=user["id"]: raise HTTPException(403,"Only the item owner can report a late return")
    if req.get("status")!="approved": raise HTTPException(409,"Only active approved loans can be marked overdue")
    if not req.get("due_date") or req["due_date"]>=date.today().isoformat(): raise HTTPException(400,"The return due date has not passed yet")
    patch("borrow_requests",request_id,{"status":"overdue"})
    return {"message":"Loan marked overdue. The borrower's trust score reflects the late return."}

@app.post("/api/ratings")
def rate_user(payload:RatingIn,x_user_id:Optional[str]=Header(default=None)):
    rater=current_user(x_user_id); req=get_doc("borrow_requests",payload.request_id)
    if not req: raise HTTPException(404,"Borrow request not found")
    if req.get("status")!="returned": raise HTTPException(400,"Users can rate each other after the item is returned")
    if rater["id"] not in (req.get("owner_id"),req.get("borrower_id")): raise HTTPException(403,"Only participants can rate this transaction")
    other=req["borrower_id"] if rater["id"]==req.get("owner_id") else req.get("owner_id")
    if payload.rated_user_id!=other: raise HTTPException(400,"You can only rate the other participant")
    rid=next_id("user_ratings")
    save("user_ratings",str(rid),{"id":rid,"request_id":payload.request_id,"rater_user_id":rater["id"],"rated_user_id":other,"rating":payload.rating,"comment":payload.comment.strip(),"created_at":now()})
    return {"message":"Rating submitted"}

@app.get("/api/users/{user_id}/ratings")
def user_ratings(user_id:str):
    ratings=[r for r in all_docs("user_ratings") if r.get("rated_user_id")==user_id]
    return sorted(ratings,key=lambda r:r.get("created_at",""),reverse=True)
