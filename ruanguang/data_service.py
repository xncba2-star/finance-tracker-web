import pandas as pd

def _data(response):
    return response.data or []

def list_workspaces(client, user_id):
    rows = _data(client.table("workspace_members")
                 .select("workspace_id,role,workspaces(id,name,type)")
                 .eq("user_id", user_id).execute())
    result=[]
    for row in rows:
        w=row.get("workspaces")
        if w:
            result.append({"id":w["id"],"name":w["name"],"type":w["type"],"role":row["role"]})
    return result

def create_workspace(client, name, kind):
    return client.rpc("create_workspace",{"p_name":name,"p_type":kind}).execute().data

def list_accounts(client,wid):
    return _data(client.table("accounts").select("*").eq("workspace_id",wid).eq("is_active",True).order("created_at").execute())

def add_account(client,wid,name,kind,opening,user_id):
    if not name:
        raise ValueError("Nama akun wajib diisi.")
    return client.table("accounts").insert({"workspace_id":wid,"name":name,"kind":kind,"opening_balance":opening,"created_by":user_id}).execute()

def delete_account(client,account_id):
    # Historical transactions are retained; account is archived instead of hard-deleted.
    return client.table("accounts").update({"is_active":False}).eq("id",account_id).execute()

def list_transactions(client,wid):
    rows=_data(client.table("transactions").select("*").eq("workspace_id",wid).order("tx_date",desc=True).order("created_at",desc=True).limit(5000).execute())
    return pd.DataFrame(rows)

def add_transaction(client,wid,kind,amount,category,account,tx_date,note,user_id,peer=None,group_id=None):
    payload={"workspace_id":wid,"kind":kind,"amount":amount,"category":category,"account":account,"tx_date":tx_date,"note":note,"created_by":user_id,"transfer_group":group_id,"transfer_peer":peer}
    return client.table("transactions").insert(payload).execute()

def add_internal_transfer(client,wid,source,target,amount,tx_date,note,user_id):
    return client.rpc("create_internal_transfer", {
        "p_workspace_id": wid,
        "p_source": source,
        "p_target": target,
        "p_amount": amount,
        "p_tx_date": tx_date,
        "p_note": note or ""
    }).execute()

def list_bills(client,wid):
    return _data(client.table("bills").select("*").eq("workspace_id",wid).order("due_date").execute())

def add_bill(client,wid,title,provider,amount,due,user_id):
    if not title:
        raise ValueError("Nama tagihan wajib diisi.")
    return client.table("bills").insert({"workspace_id":wid,"title":title,"provider":provider,"amount":amount,"due_date":due,"created_by":user_id}).execute()

def mark_bill_paid(client,bill_id):
    return client.table("bills").update({"paid":True}).eq("id",bill_id).execute()

def delete_bill(client,bill_id):
    return client.table("bills").delete().eq("id",bill_id).execute()

def invite_member(client,wid,email):
    return client.rpc("invite_workspace_member",{"p_workspace_id":wid,"p_email":email.lower()}).execute()

def list_pending_invites(client,email):
    return _data(client.table("workspace_invites").select("id,workspace_id,workspace_name").eq("invite_email",email.lower()).eq("status","pending").execute())

def accept_invite(client,invite_id):
    return client.rpc("accept_workspace_invite",{"p_invite_id":invite_id}).execute()

def get_workspace_members(client,wid):
    return _data(client.table("workspace_members").select("user_id,role,created_at").eq("workspace_id",wid).execute())

def delete_transaction(client,tx_id):
    return client.table("transactions").delete().eq("id",tx_id).execute()
