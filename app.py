import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

# --- CONFIGURATION & BUSINESS RULES ---
st.set_page_config(page_title="Mwinuka Copper Tracker", layout="wide")

WIRE_SIZES = [
    "0.50", "0.56", "0.60", "0.63", "0.65", "0.71", "0.75", "0.80", 
    "0.85", "0.90", "0.95", "1.00", "1.06", "1.12", "1.18", "1.20", 
    "1.25", "1.30", "1.40", "1.50"
]

# --- SUPABASE CLOUD CONNECTION ---
SUPABASE_URL = st.secrets.get("supabase_url", "YOUR_SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("supabase_key", "YOUR_SUPABASE_KEY")

supabase = None
if SUPABASE_URL.startswith("http"):
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"Error initializing Supabase: {e}")

def fetch_data():
    """Fetches all transactions from the cloud Supabase database."""
    if supabase is None:
        st.error("⚠️ Supabase connection is missing or invalid! Please add your Supabase URL and Key in Streamlit Secrets.")
        return pd.DataFrame()
        
    try:
        response = supabase.table("transactions").select("*").order("id", desc=True).execute()
        if response.data:
            return pd.DataFrame(response.data)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error fetching data from cloud: {e}")
        return pd.DataFrame()

def check_password():
    """Returns True if the user entered the correct password."""
    if st.session_state.get("password_correct", False):
        return True
        
    password = st.text_input("🔒 Enter Password to access this page:", type="password")
    if password == "mwinuka123":
        st.session_state["password_correct"] = True
        st.rerun()
    elif password != "":
        st.error("❌ Incorrect Password")
    return False

# --- INITIALIZE SESSION STATE MEMORY ---
if "mem_date" not in st.session_state:
    st.session_state["mem_date"] = datetime.today()
if "mem_wire" not in st.session_state:
    st.session_state["mem_wire"] = WIRE_SIZES[0]
if "mem_type" not in st.session_state:
    st.session_state["mem_type"] = "Stock In"
if "mem_price" not in st.session_state:
    st.session_state["mem_price"] = 49000

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("Mwinuka Copper")
page = st.sidebar.radio("Go to:", ["Data Entry", "Dashboard & Inventory", "✏️ Edit Records", "⚙️ Database Control"])

# --- PAGE 1: DATA ENTRY ---
if page == "Data Entry":
    st.header("📥 Record New Transaction")
    
    if check_password():
        if supabase is None:
            st.warning("⚠️ Database not connected. Please configure your Streamlit Secrets.")
            
        with st.form("entry_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                date_val = st.date_input("Date", st.session_state["mem_date"]).strftime('%Y-%m-%d')
                wire_size = st.selectbox("Wire Size (mm)", WIRE_SIZES, index=WIRE_SIZES.index(st.session_state["mem_wire"]))
                transaction_type = st.selectbox("Transaction Type", ["Stock In", "Sale"], index=["Stock In", "Sale"].index(st.session_state["mem_type"]))
            with col2:
                quantity = st.number_input("Quantity (kg)", min_value=0.0, step=0.001, format="%.3f")
                selling_price = st.selectbox("Selling Price (TZS per kg)", [49000, 60000], index=[49000, 60000].index(st.session_state["mem_price"]))

            st.markdown("---")
            st.subheader("Description (Optional)")
            col3, col4 = st.columns(2)
            with col3:
                unsealed_size = st.selectbox("Unsealed Size (mm)", [""] + WIRE_SIZES)
                lost_grams = st.number_input("Negative Grams (g)", min_value=0.0, step=1.0)
            with col4:
                comment = st.text_area("Comment / Notes", placeholder="Type any additional details here...")

            submit = st.form_submit_button("Save Transaction")
            
        # Moved OUTSIDE the form to comply with Streamlit's new rules
        if submit:
            if supabase is None:
                st.error("❌ Cannot save! Supabase connection is missing. Check Streamlit Secrets.")
            elif quantity <= 0:
                st.error("❌ Please enter a valid quantity greater than 0.")
            else:
                data_payload = {
                    "date": date_val,
                    "wire_size": wire_size,
                    "transaction_type": transaction_type,
                    "quantity": quantity,
                    "selling_price": float(selling_price),
                    "unsealed_size": unsealed_size if unsealed_size != "" else None,
                    "lost_grams": lost_grams,
                    "comment": comment if comment.strip() != "" else None
                }
                try:
                    supabase.table("transactions").insert(data_payload).execute()
                    
                    # Remember these inputs for the next entry
                    st.session_state["mem_date"] = datetime.strptime(date_val, '%Y-%m-%d')
                    st.session_state["mem_wire"] = wire_size
                    st.session_state["mem_type"] = transaction_type
                    st.session_state["mem_price"] = int(selling_price)
                    
                    st.success("✅ Transaction successfully saved to the cloud database!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Failed to save data: {e}")

# --- PAGE 2: DASHBOARD & INVENTORY ---
elif page == "Dashboard & Inventory":
    st.header("📊 Live Inventory Dashboard")
    df = fetch_data()
    
    if not df.empty:
        # Date Filter
        min_d = datetime.strptime(df['date'].min(), '%Y-%m-%d')
        max_d = datetime.strptime(df['date'].max(), '%Y-%m-%d')
        
        st.subheader("Filter Period")
        start_filter, end_filter = st.date_input("Select Date Range", [min_d, max_d])
        
        df_filtered = df[(df['date'] >= start_filter.strftime('%Y-%m-%d')) & (df['date'] <= end_filter.strftime('%Y-%m-%d'))]
        
        # Calculations
        sales_df = df_filtered[df_filtered['transaction_type'] == 'Sale']
        stock_in_df = df_filtered[df_filtered['transaction_type'] == 'Stock In']
        
        total_revenue = (sales_df['quantity'] * sales_df['selling_price']).sum()
        total_added = stock_in_df['quantity'].sum()
        total_sold = sales_df['quantity'].sum()
        total_negative_grams = df_filtered['lost_grams'].sum()
        
        # Summary Cards
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Revenue", f"{total_revenue:,.0f} TZS")
        m2.metric("Stock Added", f"{total_added:.3f} kg")
        m3.metric("Stock Sold", f"{total_sold:.3f} kg")
        m4.metric("Total Negative Grams", f"{total_negative_grams:,.0f} g")
        
        # Stock breakdown logic
        st.subheader("📦 Current Real-time Inventory Status")
        inv_data = []
        for size in sorted(WIRE_SIZES, key=float):
            size_df = df[df['wire_size'] == size]
            added = size_df[size_df['transaction_type'] == 'Stock In']['quantity'].sum()
            sold = size_df[size_df['transaction_type'] == 'Sale']['quantity'].sum()
            remaining = added - sold
            if added > 0:
                inv_data.append({"Wire Size (mm)": size, "Total In (kg)": added, "Total Out (kg)": sold, "Remaining Stock (kg)": remaining})
        
        if inv_data:
            st.dataframe(pd.DataFrame(inv_data).set_index("Wire Size (mm)"), use_container_width=True)
            
        st.subheader("📜 Recent Activity Log")
        # Removed 'comment' from the main data table display
        st.dataframe(df_filtered[['date', 'wire_size', 'transaction_type', 'quantity', 'unsealed_size', 'lost_grams']], use_container_width=True)

        st.subheader("📝 Comments & Notes Summary")
        # Filter to show only rows that actually have a comment
        comments_df = df_filtered[df_filtered['comment'].notna() & (df_filtered['comment'] != "")]
        if not comments_df.empty:
            st.dataframe(comments_df[['date', 'wire_size', 'transaction_type', 'comment']], use_container_width=True)
        else:
            st.info("No comments recorded for the selected period.")

    else:
        if supabase is not None:
            st.info("The cloud database is currently empty. Add your first transaction to view details.")

# --- PAGE 3: EDIT RECORDS ---
elif page == "✏️ Edit Records":
    st.header("✏️ Modify Cloud Transactions")
    
    if check_password():
        df = fetch_data()
        
        if not df.empty:
            search_date = st.date_input("Find logs by Date", datetime.today()).strftime('%Y-%m-%d')
            day_df = df[df['date'] == search_date]
            
            if day_df.empty:
                st.warning(f"No records found on {search_date}")
            else:
                record_options = {f"ID: {row['id']} | {row['transaction_type']} | {row['wire_size']}mm | {row['quantity']}kg": row['id'] for _, row in day_df.iterrows()}
                selected_record_label = st.selectbox("Select a row to manage:", list(record_options.keys()))
                selected_id = record_options[selected_record_label]
                
                target = df[df['id'] == selected_id].iloc[0]
                
                with st.form("edit_form"):
                    e_date = st.date_input("Edit Date", datetime.strptime(target['date'], '%Y-%m-%d')).strftime('%Y-%m-%d')
                    e_size = st.selectbox("Edit Wire Size", WIRE_SIZES, index=WIRE_SIZES.index(target['wire_size']))
                    e_type = st.selectbox("Edit Type", ["Stock In", "Sale"], index=0 if target['transaction_type'] == "Stock In" else 1)
                    e_qty = st.number_input("Edit Quantity (kg)", value=float(target['quantity']), format="%.3f")
                    e_price = st.selectbox("Edit Price", [49000, 60000], index=0 if int(target['selling_price']) == 49000 else 1)
                    e_unsealed = st.selectbox("Edit Unsealed Size", [""] + WIRE_SIZES, index=(WIRE_SIZES.index(target['unsealed_size'])+1) if target['unsealed_size'] else 0)
                    e_lost = st.number_input("Edit Negative Grams (g)", value=float(target['lost_grams'] or 0))
                    e_comment = st.text_area("Edit Comment", value=target['comment'] if target['comment'] else "")
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        save_btn = st.form_submit_button("💾 Save Changes")
                    with c2:
                        del_btn = st.form_submit_button("🗑️ Permanent Delete")
                        
                # Moved OUTSIDE the form to comply with Streamlit's new rules
                if save_btn:
                    if supabase is None:
                        st.error("❌ Cannot save! Supabase connection is missing.")
                    else:
                        update_payload = {
                            "date": e_date, "wire_size": e_size, "transaction_type": e_type, "quantity": e_qty, "selling_price": float(e_price),
                            "unsealed_size": e_unsealed if e_unsealed != "" else None, "lost_grams": e_lost, "comment": e_comment if e_comment.strip() != "" else None
                        }
                        supabase.table("transactions").update(update_payload).eq("id", selected_id).execute()
                        st.success("Record updated successfully!")
                        st.rerun()
                    
                if del_btn:
                    if supabase is None:
                        st.error("❌ Cannot delete! Supabase connection is missing.")
                    else:
                        supabase.table("transactions").delete().eq("id", selected_id).execute()
                        st.warning("Record permanently removed from cloud database.")
                        st.rerun()
        else:
            if supabase is not None:
                st.info("No records to manage.")

# --- PAGE 4: DATABASE CONTROL ---
elif page == "⚙️ Database Control":
    st.header("⚙️ Data Administration")
    
    if check_password():
        df = fetch_data()
        
        if not df.empty:
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="⬇️ Download Entire Cloud Database (CSV)",
                data=csv,
                file_name=f"copper_cloud_export_{datetime.today().strftime('%Y-%m-%d')}.csv",
                mime='text/csv',
            )
        else:
            if supabase is not None:
                st.info("No data available.")
