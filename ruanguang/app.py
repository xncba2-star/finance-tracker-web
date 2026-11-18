import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from supabase_client import get_supabase, get_auth_user, sign_in, sign_up, sign_out
from data_service import (
    list_workspaces, create_workspace, list_accounts, add_account, delete_account,
    list_transactions, add_transaction, add_internal_transfer, list_bills,
    add_bill, mark_bill_paid, delete_bill, invite_member, list_pending_invites,
    accept_invite, get_workspace_members, delete_transaction
)
from receipt_ocr import extract_receipt_text, suggest_amount

st.set_page_config(page_title="RuangUang", page_icon="💳", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap');
html,body,[class*="css"]{font-family:'DM Sans',sans-serif}
.block-container{padding-top:1.4rem;padding-bottom:5rem;max-width:1180px}
h1,h2,h3{font-family:'Manrope',sans-serif}
[data-testid="stMetric"]{background:#f5f7fb;border:1px solid #e8edf4;padding:14px;border-radius:15px}
div.stButton>button{border-radius:11px;font-weight:600;min-height:40px}
.hero{background:linear-gradient(120deg,#142b4a,#245b69);padding:24px;border-radius:20px;color:white;margin-bottom:18px}
.hero-label{color:#d4e5eb;font-size:.9rem}.hero-value{color:white;font-size:2rem;font-weight:800;margin-top:5px}
</style>
""", unsafe_allow_html=True)

def money(n):
    return "Rp " + f"{int(n or 0):,}".replace(",", ".")

def rerun():
    st.rerun()

def auth_screen():
    st.title("RuangUang")
    st.caption("Satu platform untuk mengelola keuangan pribadi dan keluarga.")
    tab_login, tab_register = st.tabs(["Login", "Buat akun"])
    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", type="primary", use_container_width=True)
            if submitted:
                try:
                    session = sign_in(email.strip(), password)
                    st.session_state["ru_session"] = {
                        "access_token": session.access_token,
                        "refresh_token": session.refresh_token
                    }
                    rerun()
                except Exception as e:
                    st.error(f"Login gagal: {e}")
    with tab_register:
        with st.form("register_form"):
            email = st.text_input("Email", key="reg_email")
            password = st.text_input("Password (minimal 8 karakter)", type="password", key="reg_password")
            confirm = st.text_input("Ulangi password", type="password")
            submitted = st.form_submit_button("Daftar", type="primary", use_container_width=True)
            if submitted:
                if password != confirm:
                    st.error("Password tidak sama.")
                elif len(password) < 8:
                    st.error("Password minimal 8 karakter.")
                else:
                    try:
                        result = sign_up(email.strip(), password)
                        if result.session:
                            st.session_state["ru_session"] = {
                                "access_token": result.session.access_token,
                                "refresh_token": result.session.refresh_token
                            }
                            rerun()
                        else:
                            st.success("Pendaftaran berhasil. Periksa email untuk verifikasi, lalu login.")
                    except Exception as e:
                        st.error(f"Pendaftaran gagal: {e}")
    st.info("Setiap akun memiliki data terpisah. Jangan gunakan password yang sama dengan mobile banking.")

if "ru_session" not in st.session_state:
    st.session_state["ru_session"] = None

if not st.session_state["ru_session"]:
    auth_screen()
    st.stop()

try:
    supabase = get_supabase(st.session_state["ru_session"])
    user = get_auth_user(supabase)
except Exception:
    st.session_state["ru_session"] = None
    st.warning("Sesi berakhir. Silakan login kembali.")
    rerun()

if not user:
    st.session_state["ru_session"] = None
    auth_screen()
    st.stop()

user_id = user.id
email = user.email or ""
workspaces = list_workspaces(supabase, user_id)

if not workspaces:
    st.title("Selamat datang di RuangUang")
    st.write("Buat ruang keuangan pribadi terlebih dahulu. Setelah itu, lu bisa membuat ruang keluarga dan mengundang anggota.")
    with st.form("first_workspace"):
        name = st.text_input("Nama ruang pribadi", value="Keuangan Saya")
        if st.form_submit_button("Buat ruang pribadi", type="primary"):
            create_workspace(supabase, name.strip(), "personal")
            rerun()
    st.stop()

# Pending invitations are tied to the authenticated email.
pending = list_pending_invites(supabase, email)
if pending:
    with st.container(border=True):
        st.subheader("Undangan ruang keluarga")
        for inv in pending:
            c1, c2 = st.columns([3,1])
            c1.write(f"Undangan ke **{inv['workspace_name']}**")
            if c2.button("Terima", key=f"accept_{inv['id']}"):
                accept_invite(supabase, inv["id"])
                rerun()

workspace_labels = {f"{w['name']} · {'Pribadi' if w['type']=='personal' else 'Keluarga'}": w for w in workspaces}
st.title("RuangUang")
st.caption("Personal and Family Finance Management")
selected_label = st.selectbox("Ruang keuangan aktif", list(workspace_labels.keys()))
workspace = workspace_labels[selected_label]
wid = workspace["id"]
role = workspace["role"]

with st.sidebar:
    st.markdown("### RuangUang")
    st.write(email)
    st.caption(f"Akses: {role}")
    if st.button("＋ Buat ruang keluarga", use_container_width=True):
        st.session_state["show_family_form"] = True
    if st.session_state.get("show_family_form"):
        with st.form("family_form"):
            family_name = st.text_input("Nama keluarga / rumah tangga")
            if st.form_submit_button("Buat ruang"):
                if family_name.strip():
                    create_workspace(supabase, family_name.strip(), "family")
                    st.session_state["show_family_form"] = False
                    rerun()
    if st.button("Logout", use_container_width=True):
        sign_out(supabase)
        st.session_state["ru_session"] = None
        rerun()

accounts = list_accounts(supabase, wid)
account_names = [a["name"] for a in accounts]
page = st.radio("Navigasi", ["🏠 Beranda","💼 Keuangan","📷 Scan Struk","📊 Analisis","👥 Anggota","⚙️ Pengaturan"], horizontal=True, label_visibility="collapsed")

def add_tx_form(kind, form_key):
    with st.form(form_key, clear_on_submit=True):
        a,b = st.columns(2)
        amount = a.number_input("Nominal (Rp)", min_value=1, step=1000, value=10000)
        tx_date = b.date_input("Tanggal", value=date.today())
        category_list = (["Uang saku","Gaji","Bonus","Bunga","Lainnya"] if kind=="Income"
                         else ["Makanan","Transportasi","Belanja","Pendidikan","Tagihan","Kesehatan","Hiburan","Lainnya"])
        category = st.selectbox("Kategori", category_list)
        account = st.selectbox("Sumber dana", account_names) if account_names else None
        note = st.text_input("Catatan (opsional)")
        if st.form_submit_button("Simpan", type="primary"):
            if not account:
                st.error("Tambahkan sumber dana terlebih dahulu.")
            else:
                add_transaction(supabase, wid, kind, amount, category, account, tx_date.isoformat(), note, user_id)
                st.success("Transaksi disimpan.")
                rerun()

if page == "🏠 Beranda":
    df = list_transactions(supabase, wid)
    balances = {a["name"]: float(a["opening_balance"]) for a in accounts}
    if not df.empty:
        for _, row in df.iterrows():
            if row["account"] in balances:
                if row["kind"] in ["Income","Transfer In"]:
                    balances[row["account"]] += float(row["amount"])
                elif row["kind"] in ["Expense","Transfer Out"]:
                    balances[row["account"]] -= float(row["amount"])
    total = sum(balances.values())
    st.markdown(f'<div class="hero"><div class="hero-label">TOTAL SALDO RUANG INI</div><div class="hero-value">{money(total)}</div><div class="hero-label">Gabungan seluruh rekening dan e-wallet dalam ruang aktif</div></div>', unsafe_allow_html=True)
    c1,c2 = st.columns(2)
    with c1:
        with st.expander("＋ Tambah pemasukan"):
            add_tx_form("Income","income_form")
    with c2:
        with st.expander("－ Tambah pengeluaran"):
            add_tx_form("Expense","expense_form")
    if not df.empty:
        today = date.today().isoformat()
        td = df[df["tx_date"] == today]
        income = td.loc[td.kind=="Income","amount"].sum()
        expense = td.loc[td.kind=="Expense","amount"].sum()
    else:
        income = expense = 0
    c1,c2 = st.columns(2)
    c1.metric("Pemasukan hari ini", money(income))
    c2.metric("Pengeluaran hari ini", money(expense))
    st.subheader("Transfer antar rekening sendiri")
    with st.expander("＋ Catat transfer internal"):
        if len(account_names) < 2:
            st.info("Tambahkan minimal dua akun.")
        else:
            with st.form("internal_transfer"):
                a,b = st.columns(2)
                source = a.selectbox("Dari", account_names)
                target = b.selectbox("Ke", [x for x in account_names if x != source])
                amount = st.number_input("Nominal (Rp)", min_value=1, step=1000)
                tx_date = st.date_input("Tanggal", value=date.today())
                note = st.text_input("Catatan")
                if st.form_submit_button("Simpan transfer", type="primary"):
                    add_internal_transfer(supabase,wid,source,target,amount,tx_date.isoformat(),note,user_id)
                    rerun()
    st.subheader("Transaksi terbaru")
    if df.empty:
        st.info("Belum ada transaksi.")
    else:
        view = df.head(15).copy()
        view["amount"] = view.apply(lambda r: ("+" if r["kind"] in ["Income","Transfer In"] else "−") + money(r["amount"]), axis=1)
        st.dataframe(view[["tx_date","kind","category","account","amount","note"]], use_container_width=True, hide_index=True)

elif page == "💼 Keuangan":
    st.subheader("Sumber keuangan")
    cols = st.columns(3)
    balances = {a["name"]: float(a["opening_balance"]) for a in accounts}
    df = list_transactions(supabase,wid)
    if not df.empty:
        for _,r in df.iterrows():
            if r["account"] in balances:
                balances[r["account"]] += float(r["amount"]) * (1 if r["kind"] in ["Income","Transfer In"] else -1)
    for i,a in enumerate(accounts):
        with cols[i%3]:
            st.metric(a["name"], money(balances.get(a["name"],0)))
            st.caption(a["kind"])
            if st.button("Hapus", key=f"delete_acc_{a['id']}"):
                delete_account(supabase,a["id"])
                rerun()
    with st.expander("＋ Tambah rekening / e-wallet"):
        with st.form("add_account",clear_on_submit=True):
            name = st.text_input("Nama sumber dana")
            kind = st.selectbox("Jenis",["Bank","E-wallet","Tunai","Lainnya"])
            opening = st.number_input("Saldo awal (Rp)",min_value=0,step=10000)
            if st.form_submit_button("Tambah",type="primary"):
                add_account(supabase,wid,name.strip(),kind,opening,user_id)
                rerun()
    st.divider()
    st.subheader("Cicilan, tagihan, dan PayLater")
    with st.expander("＋ Tambah tagihan"):
        with st.form("bill_form"):
            title = st.text_input("Nama tagihan")
            provider = st.text_input("Penyedia / untuk siapa")
            amount = st.number_input("Nominal (Rp)",min_value=1,step=10000)
            due = st.date_input("Jatuh tempo",value=date.today())
            if st.form_submit_button("Simpan tagihan"):
                add_bill(supabase,wid,title,provider,amount,due.isoformat(),user_id)
                rerun()
    for bill in list_bills(supabase,wid):
        with st.container(border=True):
            c1,c2,c3 = st.columns([3,2,1])
            c1.write(f"**{bill['title']}**")
            c1.caption(f"{bill.get('provider') or 'Tanpa penyedia'} · {bill['due_date']}")
            c2.write(money(bill["amount"]))
            c2.caption("Lunas" if bill["paid"] else "Belum lunas")
            if not bill["paid"] and c3.button("Lunas",key=f"paid_{bill['id']}"):
                mark_bill_paid(supabase,bill["id"])
                rerun()
            if c3.button("Hapus",key=f"billdel_{bill['id']}"):
                delete_bill(supabase,bill["id"])
                rerun()

elif page == "📷 Scan Struk":
    st.subheader("Scan struk belanja")
    st.write("Unggah foto struk. Periksa hasil pembacaan OCR sebelum menyimpan transaksi.")
    uploaded = st.file_uploader("Pilih foto struk",type=["png","jpg","jpeg"])
    if uploaded:
        st.image(uploaded,use_container_width=True)
        if st.button("Baca struk",type="primary"):
            with st.spinner("Membaca struk..."):
                st.session_state["receipt_text"] = extract_receipt_text(uploaded)
                st.session_state["receipt_amount"] = suggest_amount(st.session_state["receipt_text"])
        if st.session_state.get("receipt_text"):
            st.text_area("Teks hasil OCR",key="receipt_text",height=150)
            with st.form("receipt_save"):
                amount = st.number_input("Nominal (Rp)",min_value=1,value=max(1,int(st.session_state.get("receipt_amount") or 1)),step=1000)
                category = st.selectbox("Kategori",["Makanan","Belanja","Kebutuhan rumah","Transportasi","Lainnya"])
                account = st.selectbox("Dibayar dari",account_names) if account_names else None
                tx_date = st.date_input("Tanggal",value=date.today())
                if st.form_submit_button("Simpan pengeluaran",type="primary"):
                    if account:
                        add_transaction(supabase,wid,"Expense",amount,category,account,tx_date.isoformat(),"Scan struk",user_id)
                        st.session_state["receipt_text"] = ""
                        rerun()
                    else:
                        st.error("Tambahkan rekening terlebih dahulu.")
    st.caption("OCR dapat salah membaca struk. Nominal harus diperiksa manual.")

elif page == "📊 Analisis":
    st.subheader("Analisis keuangan")
    df = list_transactions(supabase,wid)
    if df.empty:
        st.info("Belum ada transaksi.")
    else:
        df["tx_date"] = pd.to_datetime(df["tx_date"])
        period = st.selectbox("Periode",["Bulan ini","30 hari terakhir","Tahun ini","Semua"])
        now = pd.Timestamp.today().normalize()
        if period=="Bulan ini":
            df=df[(df.tx_date.dt.month==now.month)&(df.tx_date.dt.year==now.year)]
        elif period=="30 hari terakhir":
            df=df[df.tx_date>=now-pd.Timedelta(days=30)]
        elif period=="Tahun ini":
            df=df[df.tx_date.dt.year==now.year]
        regular=df[df.kind.isin(["Income","Expense"])]
        inc=regular.loc[regular.kind=="Income","amount"].sum()
        exp=regular.loc[regular.kind=="Expense","amount"].sum()
        c1,c2,c3=st.columns(3)
        c1.metric("Pemasukan",money(inc)); c2.metric("Pengeluaran",money(exp)); c3.metric("Selisih",money(inc-exp))
        if not regular.empty:
            bykind=regular.groupby("kind",as_index=False)["amount"].sum()
            st.plotly_chart(px.pie(bykind,names="kind",values="amount",hole=.5,title="Pemasukan vs pengeluaran"),use_container_width=True)
            bycat=regular[regular.kind=="Expense"].groupby("category",as_index=False)["amount"].sum()
            if not bycat.empty:
                st.plotly_chart(px.bar(bycat,x="category",y="amount",title="Pengeluaran per kategori"),use_container_width=True)
        st.dataframe(df.sort_values("tx_date",ascending=False),use_container_width=True,hide_index=True)
        st.download_button("Download CSV",df.to_csv(index=False).encode("utf-8-sig"),"ruanguang_transactions.csv","text/csv")

elif page == "👥 Anggota":
    st.subheader("Anggota ruang keuangan")
    if workspace["type"] != "family":
        st.info("Undangan anggota tersedia di ruang keluarga. Buat ruang keluarga melalui sidebar.")
    else:
        st.write("Undang anggota keluarga menggunakan email akun RuangUang mereka.")
        if role in ["owner","admin"]:
            with st.form("invite_form"):
                invite_email=st.text_input("Email anggota")
                if st.form_submit_button("Kirim undangan"):
                    invite_member(supabase,wid,invite_email.strip())
                    st.success("Undangan dibuat. Anggota dapat menerimanya setelah login.")
                    rerun()
        st.dataframe(pd.DataFrame(get_workspace_members(supabase,wid)),use_container_width=True,hide_index=True)

elif page == "⚙️ Pengaturan":
    st.subheader("Pengaturan ruang")
    st.write(f"Nama: **{workspace['name']}**")
    st.write(f"Jenis: **{'Pribadi' if workspace['type']=='personal' else 'Keluarga'}**")
    st.write(f"Peran lu: **{role}**")
    st.info("Data setiap ruang dipisahkan. Anggota keluarga hanya dapat mengakses ruang yang mengundang mereka.")
    st.caption("Jangan masukkan PIN, password, atau OTP mobile banking. Versi ini tidak terhubung langsung ke bank.")
st.divider()
st.caption("RuangUang · Multi-user · Personal & Family Finance")
