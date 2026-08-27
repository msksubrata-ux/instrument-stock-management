import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import hashlib
from supabase import create_client


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Stock Management System",
    page_icon="📦",
    layout="wide"
)


# =========================================================
# SUPABASE CONNECTION
# =========================================================

@st.cache_resource
def get_supabase():

    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_SECRET_KEY"]

    return create_client(url, key)


supabase = get_supabase()


# =========================================================
# PASSWORD
# =========================================================

def hash_password(password):

    return hashlib.sha256(
        password.encode()
    ).hexdigest()


# =========================================================
# MASTER FUNCTIONS
# =========================================================

def get_instruments():

    response = (
        supabase
        .table("instruments")
        .select("instrument_name")
        .order("instrument_name")
        .execute()
    )

    return [
        row["instrument_name"]
        for row in response.data
    ]


def get_items(instrument=None):

    query = (
        supabase
        .table("items")
        .select("item_name")
    )

    if instrument:

        query = query.eq(
            "instrument_name",
            instrument
        )

    response = (
        query
        .order("item_name")
        .execute()
    )

    items = []

    for row in response.data:

        if row["item_name"] not in items:
            items.append(
                row["item_name"]
            )

    return items


def get_item_details(
    instrument,
    item
):

    response = (
        supabase
        .table("items")
        .select(
            "item_type,unit,min_stock"
        )
        .eq(
            "instrument_name",
            instrument
        )
        .eq(
            "item_name",
            item
        )
        .limit(1)
        .execute()
    )

    if response.data:
        return response.data[0]

    return None


def load_items_master():

    response = (
        supabase
        .table("items")
        .select(
            "id,"
            "instrument_name,"
            "item_name,"
            "item_type,"
            "unit,"
            "min_stock"
        )
        .order("instrument_name")
        .order("item_name")
        .execute()
    )

    return pd.DataFrame(
        response.data
    )


# =========================================================
# TRANSACTIONS
# =========================================================

def load_transactions():

    response = (
        supabase
        .table("transactions")
        .select(
            "id,"
            "txn_date,"
            "instrument_name,"
            "item_name,"
            "item_type,"
            "txn_type,"
            "quantity,"
            "remarks,"
            "username"
        )
        .order(
            "id",
            desc=False
        )
        .execute()
    )

    df = pd.DataFrame(
        response.data
    )

    if df.empty:
        return df

    df["quantity"] = pd.to_numeric(
        df["quantity"],
        errors="coerce"
    ).fillna(0)

    df["Parsed_Date"] = pd.to_datetime(
        df["txn_date"],
        errors="coerce"
    )

    df["Report_Date"] = (
        df["Parsed_Date"]
        .dt.date
    )

    df["username"] = (
        df["username"]
        .fillna("Old Entry")
        .replace("", "Old Entry")
    )

    return df


def get_current_stock(
    instrument,
    item,
    as_on_date=None
):

    df = load_transactions()

    if df.empty:
        return 0.0

    filtered = df[
        (
            df["instrument_name"]
            == instrument
        )
        &
        (
            df["item_name"]
            == item
        )
    ].copy()

    if as_on_date is not None:

        filtered = filtered[
            filtered["Report_Date"]
            <= as_on_date
        ]

    total_in = filtered.loc[
        filtered["txn_type"] == "IN",
        "quantity"
    ].sum()

    total_out = filtered.loc[
        filtered["txn_type"] == "OUT",
        "quantity"
    ].sum()

    return float(
        total_in - total_out
    )


# =========================================================
# DATE RANGE
# =========================================================

def date_range_controls(prefix):

    col1, col2 = st.columns(2)

    with col1:

        from_date = st.date_input(
            "From Date",
            value=date(
                date.today().year,
                1,
                1
            ),
            key=f"{prefix}_from"
        )

    with col2:

        to_date = st.date_input(
            "To Date",
            value=date.today(),
            key=f"{prefix}_to"
        )

    if from_date > to_date:

        st.error(
            "From Date cannot be "
            "greater than To Date."
        )

        st.stop()

    return from_date, to_date


def filter_date_range(
    df,
    from_date,
    to_date
):

    if df.empty:
        return df

    return df[
        (
            df["Report_Date"]
            >= from_date
        )
        &
        (
            df["Report_Date"]
            <= to_date
        )
    ].copy()


# =========================================================
# SESSION
# =========================================================

if "logged_in" not in st.session_state:

    st.session_state.logged_in = False

if "username" not in st.session_state:

    st.session_state.username = ""

if "role" not in st.session_state:

    st.session_state.role = ""

if "permissions" not in st.session_state:

    st.session_state.permissions = {}


# =========================================================
# LOGIN
# =========================================================

def login_page():

    st.title(
        "🔐 Stock Management Login"
    )

    username = st.text_input(
        "Username"
    )

    password = st.text_input(
        "Password",
        type="password"
    )

    if st.button(
        "Login",
        type="primary"
    ):

        response = (
            supabase
            .table("users")
            .select("*")
            .eq(
                "username",
                username.strip()
            )
            .limit(1)
            .execute()
        )

        if not response.data:

            st.error(
                "Wrong Username or Password."
            )

            return

        user = response.data[0]

        if int(
            user.get(
                "active",
                0
            )
        ) != 1:

            st.error(
                "This User is Inactive."
            )

            return

        if (
            user["password"]
            != hash_password(password)
        ):

            st.error(
                "Wrong Username or Password."
            )

            return

        st.session_state.logged_in = True

        st.session_state.username = (
            user["username"]
        )

        st.session_state.role = (
            user["role"]
        )

        st.session_state.permissions = {
            "Dashboard":
                bool(
                    user.get(
                        "can_dashboard",
                        0
                    )
                ),

            "Instrument Master":
                bool(
                    user.get(
                        "can_instrument",
                        0
                    )
                ),

            "Item Master":
                bool(
                    user.get(
                        "can_item",
                        0
                    )
                ),

            "Stock IN":
                bool(
                    user.get(
                        "can_stock_in",
                        0
                    )
                ),

            "Stock OUT":
                bool(
                    user.get(
                        "can_stock_out",
                        0
                    )
                ),

            "Current Stock":
                bool(
                    user.get(
                        "can_current_stock",
                        0
                    )
                ),

            "Reports":
                bool(
                    user.get(
                        "can_reports",
                        0
                    )
                ),

            "Transaction Report":
                bool(
                    user.get(
                        "can_transaction_report",
                        0
                    )
                ),

            "User Management":
                bool(
                    user.get(
                        "can_user_management",
                        0
                    )
                )
        }

        st.rerun()


if not st.session_state.logged_in:

    login_page()
    st.stop()


# =========================================================
# HEADER
# =========================================================

st.title(
    "📦 Instrument Wise Stock Management System"
)

st.caption(
    "Online Stock System | "
    "Supabase Database"
)


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title(
    "📦 STOCK SYSTEM"
)

st.sidebar.write(
    f"👤 User: "
    f"{st.session_state.username}"
)

st.sidebar.write(
    f"🔑 Role: "
    f"{st.session_state.role}"
)

st.sidebar.success(
    "🌐 Online Database"
)

if st.sidebar.button(
    "🚪 Logout"
):

    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.permissions = {}

    st.rerun()

st.sidebar.divider()


# =========================================================
# MENU PERMISSION
# =========================================================

all_menus = [
    "Dashboard",
    "Instrument Master",
    "Item Master",
    "Stock IN",
    "Stock OUT",
    "Current Stock",
    "Reports",
    "Transaction Report",
    "User Management"
]

menu_options = [
    menu_name
    for menu_name in all_menus
    if st.session_state.permissions.get(
        menu_name,
        False
    )
]

if not menu_options:

    st.error(
        "No Menu Permission assigned."
    )

    st.stop()


menu = st.sidebar.radio(
    "Select Menu",
    menu_options
)


# =========================================================
# DASHBOARD
# =========================================================

if menu == "Dashboard":

    st.header(
        "📊 Dashboard"
    )

    instruments = get_instruments()

    master_df = load_items_master()

    tx_df = load_transactions()

    instrument_count = len(
        instruments
    )

    item_count = len(
        master_df
    )

    transaction_count = len(
        tx_df
    )

    low_stock_count = 0

    if not master_df.empty:

        for _, row in master_df.iterrows():

            stock = get_current_stock(
                row["instrument_name"],
                row["item_name"]
            )

            if (
                stock
                <= float(
                    row["min_stock"]
                    or 0
                )
            ):

                low_stock_count += 1

    c1, c2, c3, c4 = (
        st.columns(4)
    )

    c1.metric(
        "🔧 Instruments",
        instrument_count
    )

    c2.metric(
        "🧰 Items",
        item_count
    )

    c3.metric(
        "📋 Transactions",
        transaction_count
    )

    c4.metric(
        "⚠️ Low Stock",
        low_stock_count
    )


# =========================================================
# INSTRUMENT MASTER
# =========================================================

elif menu == "Instrument Master":

    st.header(
        "🔧 Instrument Master"
    )

    tab1, tab2 = st.tabs(
        [
            "Add Instrument",
            "Edit / Delete"
        ]
    )


    # ---------------- ADD ----------------

    with tab1:

        with st.form(
            "add_instrument",
            clear_on_submit=True
        ):

            instrument_name = (
                st.text_input(
                    "Instrument Name"
                )
            )

            add_button = (
                st.form_submit_button(
                    "➕ Add Instrument"
                )
            )

        if add_button:

            name = (
                instrument_name
                .strip()
            )

            if not name:

                st.warning(
                    "Enter Instrument Name."
                )

            elif name in get_instruments():

                st.error(
                    "Instrument already exists."
                )

            else:

                supabase.table(
                    "instruments"
                ).insert(
                    {
                        "instrument_name":
                            name
                    }
                ).execute()

                st.success(
                    "Instrument added."
                )

                st.rerun()


    # ---------------- EDIT DELETE ----------------

    with tab2:

        instruments = (
            get_instruments()
        )

        if not instruments:

            st.info(
                "No Instruments available."
            )

        else:

            selected = st.selectbox(
                "Select Instrument",
                instruments,
                key="edit_inst"
            )

            new_name = st.text_input(
                "Instrument Name",
                value=selected
            )

            c1, c2 = st.columns(2)

            with c1:

                if st.button(
                    "💾 Update Instrument"
                ):

                    clean_name = (
                        new_name.strip()
                    )

                    if not clean_name:

                        st.warning(
                            "Enter Instrument Name."
                        )

                    elif (
                        clean_name != selected
                        and
                        clean_name
                        in instruments
                    ):

                        st.error(
                            "Instrument already exists."
                        )

                    else:

                        (
                            supabase
                            .table("instruments")
                            .update({
                                "instrument_name":
                                    clean_name
                            })
                            .eq(
                                "instrument_name",
                                selected
                            )
                            .execute()
                        )

                        (
                            supabase
                            .table("items")
                            .update({
                                "instrument_name":
                                    clean_name
                            })
                            .eq(
                                "instrument_name",
                                selected
                            )
                            .execute()
                        )

                        (
                            supabase
                            .table("transactions")
                            .update({
                                "instrument_name":
                                    clean_name
                            })
                            .eq(
                                "instrument_name",
                                selected
                            )
                            .execute()
                        )

                        st.success(
                            "Instrument updated."
                        )

                        st.rerun()


            with c2:

                confirm = st.checkbox(
                    "Confirm Delete",
                    key="inst_delete_confirm"
                )

                if st.button(
                    "🗑 Delete Instrument"
                ):

                    if not confirm:

                        st.warning(
                            "Tick Confirm Delete."
                        )

                    else:

                        response = (
                            supabase
                            .table("items")
                            .select(
                                "id",
                                count="exact"
                            )
                            .eq(
                                "instrument_name",
                                selected
                            )
                            .execute()
                        )

                        if (
                            response.count
                            and
                            response.count > 0
                        ):

                            st.error(
                                "Cannot delete. "
                                "Items exist under "
                                "this Instrument."
                            )

                        else:

                            (
                                supabase
                                .table("instruments")
                                .delete()
                                .eq(
                                    "instrument_name",
                                    selected
                                )
                                .execute()
                            )

                            st.success(
                                "Instrument deleted."
                            )

                            st.rerun()


    response = (
        supabase
        .table("instruments")
        .select(
            "id,instrument_name"
        )
        .order("instrument_name")
        .execute()
    )

    df = pd.DataFrame(
        response.data
    )

    if not df.empty:

        df.columns = [
            "ID",
            "Instrument"
        ]

    st.dataframe(
        df,
        width="stretch",
        hide_index=True
    )


# =========================================================
# ITEM MASTER
# =========================================================

elif menu == "Item Master":

    st.header(
        "🧰 Spare / Consumable Master"
    )

    instruments = get_instruments()

    if not instruments:

        st.warning(
            "First add an Instrument."
        )

    else:

        tab1, tab2 = st.tabs(
            [
                "Add Item",
                "Edit / Delete"
            ]
        )


        # ---------------- ADD ITEM ----------------

        with tab1:

            with st.form(
                "add_item_form",
                clear_on_submit=True
            ):

                instrument = st.selectbox(
                    "Instrument",
                    instruments
                )

                item_name = st.text_input(
                    "Spare / Consumable Name"
                )

                item_type = st.selectbox(
                    "Item Type",
                    [
                        "Spare",
                        "Consumable"
                    ]
                )

                unit = st.selectbox(
                    "Unit",
                    [
                        "Nos",
                        "Pcs",
                        "Set",
                        "Box",
                        "Packet",
                        "Bottle",
                        "Ltr",
                        "Kg",
                        "Gram",
                        "Meter",
                        "Roll",
                        "Pair",
                        "Other"
                    ]
                )

                min_stock = st.number_input(
                    "Minimum Stock",
                    min_value=0.0,
                    value=0.0,
                    step=1.0
                )

                save_item = (
                    st.form_submit_button(
                        "➕ Add Item"
                    )
                )

            if save_item:

                clean_item = (
                    item_name.strip()
                )

                existing = get_items(
                    instrument
                )

                if not clean_item:

                    st.warning(
                        "Enter Item Name."
                    )

                elif clean_item in existing:

                    st.error(
                        "Item already exists."
                    )

                else:

                    (
                        supabase
                        .table("items")
                        .insert({
                            "instrument_name":
                                instrument,

                            "item_name":
                                clean_item,

                            "item_type":
                                item_type,

                            "unit":
                                unit,

                            "min_stock":
                                min_stock
                        })
                        .execute()
                    )

                    st.success(
                        "Item added."
                    )

                    st.rerun()


        # ---------------- EDIT ITEM ----------------

        with tab2:

            edit_instrument = (
                st.selectbox(
                    "Instrument",
                    instruments,
                    key="edit_item_inst"
                )
            )

            items = get_items(
                edit_instrument
            )

            if not items:

                st.info(
                    "No Items available."
                )

            else:

                selected_item = (
                    st.selectbox(
                        "Item",
                        items,
                        key="edit_item_name"
                    )
                )

                details = (
                    get_item_details(
                        edit_instrument,
                        selected_item
                    )
                )

                new_item_name = (
                    st.text_input(
                        "Item Name",
                        value=selected_item
                    )
                )

                type_options = [
                    "Spare",
                    "Consumable"
                ]

                new_type = st.selectbox(
                    "Item Type",
                    type_options,
                    index=(
                        type_options
                        .index(
                            details[
                                "item_type"
                            ]
                        )
                    )
                )

                units = [
                    "Nos",
                    "Pcs",
                    "Set",
                    "Box",
                    "Packet",
                    "Bottle",
                    "Ltr",
                    "Kg",
                    "Gram",
                    "Meter",
                    "Roll",
                    "Pair",
                    "Other"
                ]

                current_unit = (
                    details["unit"]
                )

                if current_unit not in units:
                    units.append(
                        current_unit
                    )

                new_unit = st.selectbox(
                    "Unit",
                    units,
                    index=units.index(
                        current_unit
                    )
                )

                new_minimum = (
                    st.number_input(
                        "Minimum Stock",
                        min_value=0.0,
                        value=float(
                            details[
                                "min_stock"
                            ]
                            or 0
                        ),
                        step=1.0
                    )
                )

                c1, c2 = st.columns(2)

                with c1:

                    if st.button(
                        "💾 Update Item"
                    ):

                        clean_name = (
                            new_item_name
                            .strip()
                        )

                        if not clean_name:

                            st.warning(
                                "Enter Item Name."
                            )

                        else:

                            (
                                supabase
                                .table("items")
                                .update({
                                    "item_name":
                                        clean_name,

                                    "item_type":
                                        new_type,

                                    "unit":
                                        new_unit,

                                    "min_stock":
                                        new_minimum
                                })
                                .eq(
                                    "instrument_name",
                                    edit_instrument
                                )
                                .eq(
                                    "item_name",
                                    selected_item
                                )
                                .execute()
                            )

                            (
                                supabase
                                .table(
                                    "transactions"
                                )
                                .update({
                                    "item_name":
                                        clean_name,

                                    "item_type":
                                        new_type
                                })
                                .eq(
                                    "instrument_name",
                                    edit_instrument
                                )
                                .eq(
                                    "item_name",
                                    selected_item
                                )
                                .execute()
                            )

                            st.success(
                                "Item updated."
                            )

                            st.rerun()


                with c2:

                    confirm = st.checkbox(
                        "Confirm Delete",
                        key="item_delete"
                    )

                    if st.button(
                        "🗑 Delete Item"
                    ):

                        if not confirm:

                            st.warning(
                                "Tick Confirm Delete."
                            )

                        else:

                            stock = (
                                get_current_stock(
                                    edit_instrument,
                                    selected_item
                                )
                            )

                            if stock != 0:

                                st.error(
                                    "Cannot delete because "
                                    "Stock exists."
                                )

                            else:

                                (
                                    supabase
                                    .table("items")
                                    .delete()
                                    .eq(
                                        "instrument_name",
                                        edit_instrument
                                    )
                                    .eq(
                                        "item_name",
                                        selected_item
                                    )
                                    .execute()
                                )

                                st.success(
                                    "Item deleted."
                                )

                                st.rerun()


    item_df = load_items_master()

    if not item_df.empty:

        item_df = item_df.rename(
            columns={
                "id": "ID",
                "instrument_name":
                    "Instrument",
                "item_name": "Item",
                "item_type": "Type",
                "unit": "Unit",
                "min_stock":
                    "Minimum Stock"
            }
        )

    st.dataframe(
        item_df,
        width="stretch",
        hide_index=True
    )


# =========================================================
# STOCK IN
# =========================================================

elif menu == "Stock IN":

    st.header(
        "📥 Stock IN"
    )

    instruments = get_instruments()

    if not instruments:

        st.warning(
            "No Instrument available."
        )

else:

    if st.session_state.pop("reset_stock_in", False):
        st.session_state["stock_in_instrument"] = "-- Select Instrument --"
        st.session_state["stock_in_item"] = "-- Select Item --"
        st.session_state["stock_in_qty"] = 1.0
        st.session_state["stock_in_rate"] = 0.0
        st.session_state["stock_in_remarks"] = ""

    instrument_options = ["-- Select Instrument --"] + instruments

    instrument = st.selectbox(
        "Instrument",
        instrument_options,
        key="stock_in_instrument"
    )
    
    items = get_items(
    instrument
    )
    
    if not items:
    st.warning(
        "No Item available."
    )
else:
    item_options = ["-- Select Item --"] + items

    item = st.selectbox(
        "Item",
        item_options,
        key="stock_in_item"
    )

    if item == "-- Select Item --":
        st.info("Please select an Item.")
        st.stop()

    details = get_item_details(
        instrument,
        item
    )
           
            item_type = (
                details["item_type"]
            )

            current_stock = (
                get_current_stock(
                    instrument,
                    item
                )
            )

            st.write(
                f"**Type:** {item_type}"
            )

            st.metric(
                "Current Stock",
                current_stock
            )
           

        
            quantity = st.number_input(
                "Quantity",
                min_value=0.01,
                value=1.0,
                step=1.0,
                key="stock_in_qty"
            )
            rate = st.number_input(
                "Rate (₹)",
                min_value=0.0,
                value=0.0,
                step=1.0,
                key="stock_in_rate"
            )

            total_value = quantity * rate

            st.write(
                f"**Total Value: ₹{total_value:,.2f}**"
            )
            remarks = st.text_input(
                "Supplier / PO No. / Remarks",
                key="stock_in_remarks"
            )

            if st.button(
                "💾 Save Stock IN",
                type="primary"
            ):

                (
                    supabase
                    .table("transactions")
                    .insert({
                        "txn_date":
                            datetime.now()
                            .astimezone()
                            .isoformat(),

                        "instrument_name":
                            instrument,

                        "item_name":
                            item,

                        "item_type":
                            item_type,

                        "txn_type":
                            "IN",

                        "quantity":
                            quantity,
                    "rate":
                        rate,
                        
                        "remarks":
                            remarks.strip(),

                        "username":
                            st.session_state
                            .username
                    })
                    .execute()
                )

                st.success(
                    "Stock IN saved."
                )

                st.session_state["reset_stock_in"] = True

                st.rerun()


# =========================================================
# STOCK OUT
# =========================================================

elif menu == "Stock OUT":

    st.header(
        "📤 Stock OUT"
    )

    instruments = get_instruments()

    if not instruments:

        st.warning(
            "No Instrument available."
        )

    else:

        instrument = st.selectbox(
            "Instrument",
            instruments
        )

        items = get_items(
            instrument
        )

        if not items:

            st.warning(
                "No Item available."
            )

        else:

            item = st.selectbox(
                "Item",
                items
            )

            details = get_item_details(
                instrument,
                item
            )

            item_type = (
                details["item_type"]
            )

            available = get_current_stock(
                instrument,
                item
            )

            st.write(
                f"**Type:** {item_type}"
            )

            st.metric(
                "Available Stock",
                available
            )

            quantity = st.number_input(
                "Quantity",
                min_value=0.01,
                value=1.0,
                step=1.0
            )

            remarks = st.text_input(
                "Issued To / Department / Remarks"
            )

            if st.button(
                "💾 Save Stock OUT",
                type="primary"
            ):

                if quantity > available:

                    st.error(
                        f"Insufficient Stock. "
                        f"Available: {available}"
                    )

                else:

                    (
                        supabase
                        .table("transactions")
                        .insert({
                            "txn_date":
                                datetime.now()
                                .astimezone()
                                .isoformat(),

                            "instrument_name":
                                instrument,

                            "item_name":
                                item,

                            "item_type":
                                item_type,

                            "txn_type":
                                "OUT",

                            "quantity":
                                quantity,

                            "remarks":
                                remarks.strip(),

                            "username":
                                st.session_state
                                .username
                        })
                        .execute()
                    )

                    st.success(
                        "Stock OUT saved."
                    )

                    st.rerun()


# =========================================================
# CURRENT STOCK
# =========================================================

elif menu == "Current Stock":

    st.header(
        "📦 Current Stock Report"
    )

    from_date, to_date = (
        date_range_controls(
            "current_stock"
        )
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        instrument_filter = (
            st.selectbox(
                "Instrument",
                ["ALL"]
                + get_instruments()
            )
        )

    with c2:

        type_filter = st.selectbox(
            "Item Type",
            [
                "ALL",
                "Spare",
                "Consumable"
            ]
        )

    with c3:

        status_filter = st.selectbox(
            "Status",
            [
                "ALL",
                "OK",
                "LOW STOCK"
            ]
        )

    master = load_items_master()

    tx = load_transactions()

    period_tx = filter_date_range(
        tx,
        from_date,
        to_date
    )

    rows = []

    if not master.empty:

        for _, row in master.iterrows():

            inst = (
                row[
                    "instrument_name"
                ]
            )

            item = row["item_name"]

            if period_tx.empty:

                item_tx = period_tx

            else:

                item_tx = period_tx[
                    (
                        period_tx[
                            "instrument_name"
                        ] == inst
                    )
                    &
                    (
                        period_tx[
                            "item_name"
                        ] == item
                    )
                ]

            total_in = 0
            total_out = 0

            if not item_tx.empty:

                total_in = (
                    item_tx.loc[
                        item_tx[
                            "txn_type"
                        ] == "IN",
                        "quantity"
                    ].sum()
                )

                total_out = (
                    item_tx.loc[
                        item_tx[
                            "txn_type"
                        ] == "OUT",
                        "quantity"
                    ].sum()
                )

            stock_as_on = (
                get_current_stock(
                    inst,
                    item,
                    to_date
                )
            )

            minimum = float(
                row["min_stock"]
                or 0
            )

            status = (
                "LOW STOCK"
                if stock_as_on
                <= minimum
                else "OK"
            )

            rows.append({
                "Instrument": inst,
                "Item": item,
                "Type":
                    row["item_type"],
                "Unit":
                    row["unit"],
                "Period IN":
                    total_in,
                "Period OUT":
                    total_out,
                "Stock As On":
                    stock_as_on,
                "Minimum Stock":
                    minimum,
                "Status":
                    status
            })

    report_df = pd.DataFrame(
        rows
    )

    if not report_df.empty:

        if instrument_filter != "ALL":

            report_df = report_df[
                report_df[
                    "Instrument"
                ] == instrument_filter
            ]

        if type_filter != "ALL":

            report_df = report_df[
                report_df["Type"]
                == type_filter
            ]

        if status_filter != "ALL":

            report_df = report_df[
                report_df["Status"]
                == status_filter
            ]

    st.dataframe(
        report_df,
        width="stretch",
        hide_index=True
    )

    csv = report_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "⬇️ Download Current Stock",
        csv,
        "current_stock_report.csv",
        "text/csv"
    )


# =========================================================
# REPORTS
# =========================================================

elif menu == "Reports":

    st.header(
        "📊 Reports"
    )

    report_name = st.selectbox(
        "Select Report",
        [
            "Instrument Wise Report",
            "Stock Wise Report",
            "User Wise Report"
        ]
    )


    # =====================================================
    # INSTRUMENT WISE
    # =====================================================

    if (
        report_name
        == "Instrument Wise Report"
    ):

        st.subheader(
            "🔧 Instrument Wise Report"
        )

        from_date, to_date = (
            date_range_controls(
                "instrument_report"
            )
        )

        c1, c2, c3 = (
            st.columns(3)
        )

        with c1:

            instrument_filter = (
                st.selectbox(
                    "Instrument",
                    ["ALL"]
                    + get_instruments()
                )
            )

        with c2:

            type_filter = (
                st.selectbox(
                    "Item Type",
                    [
                        "ALL",
                        "Spare",
                        "Consumable"
                    ]
                )
            )

        with c3:

            item_filter = (
                st.selectbox(
                    "Item",
                    ["ALL"]
                    + get_items()
                )
            )

        master = load_items_master()

        tx = load_transactions()

        period_tx = filter_date_range(
            tx,
            from_date,
            to_date
        )

        rows = []

        if not master.empty:

            for _, row in master.iterrows():

                inst = row[
                    "instrument_name"
                ]

                item = row[
                    "item_name"
                ]

                if period_tx.empty:

                    item_tx = period_tx

                else:

                    item_tx = period_tx[
                        (
                            period_tx[
                                "instrument_name"
                            ] == inst
                        )
                        &
                        (
                            period_tx[
                                "item_name"
                            ] == item
                        )
                    ]

                total_in = 0
                total_out = 0

                if not item_tx.empty:

                    total_in = (
                        item_tx.loc[
                            item_tx[
                                "txn_type"
                            ] == "IN",
                            "quantity"
                        ].sum()
                    )

                    total_out = (
                        item_tx.loc[
                            item_tx[
                                "txn_type"
                            ] == "OUT",
                            "quantity"
                        ].sum()
                    )

                stock_as_on = (
                    get_current_stock(
                        inst,
                        item,
                        to_date
                    )
                )

                minimum = float(
                    row[
                        "min_stock"
                    ]
                    or 0
                )

                status = (
                    "LOW STOCK"
                    if stock_as_on
                    <= minimum
                    else "OK"
                )

                rows.append({
                    "Instrument": inst,
                    "Item": item,
                    "Type":
                        row[
                            "item_type"
                        ],
                    "Unit":
                        row["unit"],
                    "Total IN":
                        total_in,
                    "Total OUT":
                        total_out,
                    "Stock As On":
                        stock_as_on,
                    "Minimum Stock":
                        minimum,
                    "Status":
                        status
                })

        report_df = (
            pd.DataFrame(rows)
        )

        if not report_df.empty:

            if (
                instrument_filter
                != "ALL"
            ):

                report_df = (
                    report_df[
                        report_df[
                            "Instrument"
                        ]
                        == instrument_filter
                    ]
                )

            if type_filter != "ALL":

                report_df = (
                    report_df[
                        report_df[
                            "Type"
                        ]
                        == type_filter
                    ]
                )

            if item_filter != "ALL":

                report_df = (
                    report_df[
                        report_df[
                            "Item"
                        ]
                        == item_filter
                    ]
                )

        st.dataframe(
            report_df,
            width="stretch",
            hide_index=True
        )

        csv = report_df.to_csv(
            index=False
        ).encode("utf-8")

        st.download_button(
            "⬇️ Download Instrument Wise Report",
            csv,
            "instrument_wise_report.csv",
            "text/csv"
        )


    # =====================================================
    # STOCK WISE
    # =====================================================

    elif (
        report_name
        == "Stock Wise Report"
    ):

        st.subheader(
            "📦 Stock Wise Report"
        )

        from_date, to_date = (
            date_range_controls(
                "stock_report"
            )
        )

        c1, c2, c3 = (
            st.columns(3)
        )

        with c1:

            instrument_filter = (
                st.selectbox(
                    "Instrument",
                    ["ALL"]
                    + get_instruments()
                )
            )

        with c2:

            type_filter = (
                st.selectbox(
                    "Item Type",
                    [
                        "ALL",
                        "Spare",
                        "Consumable"
                    ]
                )
            )

        with c3:

            item_filter = (
                st.selectbox(
                    "Item",
                    ["ALL"]
                    + get_items()
                )
            )

        master = load_items_master()

        tx = load_transactions()

        period_tx = filter_date_range(
            tx,
            from_date,
            to_date
        )

        rows = []

        if not master.empty:

            for _, row in master.iterrows():

                inst = row[
                    "instrument_name"
                ]

                item = row[
                    "item_name"
                ]

                if period_tx.empty:

                    item_tx = period_tx

                else:

                    item_tx = period_tx[
                        (
                            period_tx[
                                "instrument_name"
                            ] == inst
                        )
                        &
                        (
                            period_tx[
                                "item_name"
                            ] == item
                        )
                    ]

                total_in = 0
                total_out = 0

                if not item_tx.empty:

                    total_in = (
                        item_tx.loc[
                            item_tx[
                                "txn_type"
                            ] == "IN",
                            "quantity"
                        ].sum()
                    )

                    total_out = (
                        item_tx.loc[
                            item_tx[
                                "txn_type"
                            ] == "OUT",
                            "quantity"
                        ].sum()
                    )

                opening_date = (
                    from_date
                    - timedelta(days=1)
                )

                opening_stock = (
                    get_current_stock(
                        inst,
                        item,
                        opening_date
                    )
                )

                closing_stock = (
                    opening_stock
                    + total_in
                    - total_out
                )

                minimum = float(
                    row["min_stock"]
                    or 0
                )

                status = (
                    "LOW STOCK"
                    if closing_stock
                    <= minimum
                    else "OK"
                )

                rows.append({
                    "Instrument":
                        inst,
                    "Item":
                        item,
                    "Type":
                        row[
                            "item_type"
                        ],
                    "Unit":
                        row["unit"],
                    "Opening Stock":
                        opening_stock,
                    "Stock IN":
                        total_in,
                    "Stock OUT":
                        total_out,
                    "Closing Stock":
                        closing_stock,
                    "Minimum Stock":
                        minimum,
                    "Status":
                        status
                })

        report_df = (
            pd.DataFrame(rows)
        )

        if not report_df.empty:

            if (
                instrument_filter
                != "ALL"
            ):

                report_df = (
                    report_df[
                        report_df[
                            "Instrument"
                        ]
                        == instrument_filter
                    ]
                )

            if type_filter != "ALL":

                report_df = (
                    report_df[
                        report_df[
                            "Type"
                        ]
                        == type_filter
                    ]
                )

            if item_filter != "ALL":

                report_df = (
                    report_df[
                        report_df[
                            "Item"
                        ]
                        == item_filter
                    ]
                )

        st.dataframe(
            report_df,
            width="stretch",
            hide_index=True
        )

        csv = report_df.to_csv(
            index=False
        ).encode("utf-8")

        st.download_button(
            "⬇️ Download Stock Wise Report",
            csv,
            "stock_wise_report.csv",
            "text/csv"
        )


    # =====================================================
    # USER WISE
    # =====================================================

    elif (
        report_name
        == "User Wise Report"
    ):

        st.subheader(
            "👤 User Wise Report"
        )

        from_date, to_date = (
            date_range_controls(
                "user_report"
            )
        )

        tx = load_transactions()

        filtered = filter_date_range(
            tx,
            from_date,
            to_date
        )

        usernames = []

        if not tx.empty:

            usernames = sorted(
                tx["username"]
                .dropna()
                .unique()
                .tolist()
            )

        c1, c2 = st.columns(2)

        with c1:

            user_filter = (
                st.selectbox(
                    "User",
                    ["ALL"]
                    + usernames
                )
            )

        with c2:

            instrument_filter = (
                st.selectbox(
                    "Instrument",
                    ["ALL"]
                    + get_instruments()
                )
            )

        c3, c4 = st.columns(2)

        with c3:

            type_filter = (
                st.selectbox(
                    "Item Type",
                    [
                        "ALL",
                        "Spare",
                        "Consumable"
                    ]
                )
            )

        with c4:

            txn_filter = (
                st.selectbox(
                    "Transaction Type",
                    [
                        "ALL",
                        "IN",
                        "OUT"
                    ]
                )
            )

        if not filtered.empty:

            if user_filter != "ALL":

                filtered = filtered[
                    filtered[
                        "username"
                    ] == user_filter
                ]

            if (
                instrument_filter
                != "ALL"
            ):

                filtered = filtered[
                    filtered[
                        "instrument_name"
                    ]
                    == instrument_filter
                ]

            if type_filter != "ALL":

                filtered = filtered[
                    filtered[
                        "item_type"
                    ] == type_filter
                ]

            if txn_filter != "ALL":

                filtered = filtered[
                    filtered[
                        "txn_type"
                    ] == txn_filter
                ]

        if filtered.empty:

            user_df = pd.DataFrame(
                columns=[
                    "Date",
                    "User",
                    "Instrument",
                    "Item",
                    "Type",
                    "Transaction",
                    "Quantity",
                    "Remarks"
                ]
            )

        else:

            user_df = filtered[
                [
                    "txn_date",
                    "username",
                    "instrument_name",
                    "item_name",
                    "item_type",
                    "txn_type",
                    "quantity",
                    "remarks"
                ]
            ].copy()

            user_df.columns = [
                "Date",
                "User",
                "Instrument",
                "Item",
                "Type",
                "Transaction",
                "Quantity",
                "Remarks"
            ]

        st.dataframe(
            user_df,
            width="stretch",
            hide_index=True
        )

        csv = user_df.to_csv(
            index=False
        ).encode("utf-8")

        st.download_button(
            "⬇️ Download User Wise Report",
            csv,
            "user_wise_report.csv",
            "text/csv"
        )


# =========================================================
# TRANSACTION REPORT
# =========================================================

elif menu == "Transaction Report":

    st.header(
        "📋 Transaction Report"
    )

    from_date, to_date = (
        date_range_controls(
            "transaction_report"
        )
    )

    tx = load_transactions()

    filtered = filter_date_range(
        tx,
        from_date,
        to_date
    )

    usernames = []

    if not tx.empty:

        usernames = sorted(
            tx["username"]
            .dropna()
            .unique()
            .tolist()
        )

    c1, c2 = st.columns(2)

    with c1:

        instrument_filter = (
            st.selectbox(
                "Instrument",
                ["ALL"]
                + get_instruments()
            )
        )

    with c2:

        type_filter = (
            st.selectbox(
                "Item Type",
                [
                    "ALL",
                    "Spare",
                    "Consumable"
                ]
            )
        )

    c3, c4 = st.columns(2)

    with c3:

        txn_filter = (
            st.selectbox(
                "Transaction Type",
                [
                    "ALL",
                    "IN",
                    "OUT"
                ]
            )
        )

    with c4:

        user_filter = (
            st.selectbox(
                "User",
                ["ALL"]
                + usernames
            )
        )

    if not filtered.empty:

        if instrument_filter != "ALL":

            filtered = filtered[
                filtered[
                    "instrument_name"
                ] == instrument_filter
            ]

        if type_filter != "ALL":

            filtered = filtered[
                filtered[
                    "item_type"
                ] == type_filter
            ]

        if txn_filter != "ALL":

            filtered = filtered[
                filtered[
                    "txn_type"
                ] == txn_filter
            ]

        if user_filter != "ALL":

            filtered = filtered[
                filtered[
                    "username"
                ] == user_filter
            ]

    if filtered.empty:

        display_df = pd.DataFrame(
            columns=[
                "ID",
                "Date",
                "User",
                "Instrument",
                "Item",
                "Type",
                "Transaction",
                "Quantity",
                "Remarks"
            ]
        )

    else:

        display_df = filtered[
            [
                "id",
                "txn_date",
                "username",
                "instrument_name",
                "item_name",
                "item_type",
                "txn_type",
                "quantity",
                "remarks"
            ]
        ].copy()

        display_df.columns = [
            "ID",
            "Date",
            "User",
            "Instrument",
            "Item",
            "Type",
            "Transaction",
            "Quantity",
            "Remarks"
        ]

        display_df = (
            display_df.sort_values(
                "ID",
                ascending=False
            )
        )

    st.dataframe(
        display_df,
        width="stretch",
        hide_index=True
    )

    csv = display_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "⬇️ Download Transaction Report",
        csv,
        "transaction_report.csv",
        "text/csv"
    )


# =========================================================
# USER MANAGEMENT
# =========================================================

elif menu == "User Management":

    st.header(
        "👥 User Management"
    )

    tab1, tab2 = st.tabs(
        [
            "➕ Create User",
            "✏️ Manage User"
        ]
    )


    # =====================================================
    # CREATE USER
    # =====================================================

    with tab1:

        with st.form(
            "create_user"
        ):

            new_username = st.text_input(
                "Username"
            )

            new_password = st.text_input(
                "Password",
                type="password"
            )

            confirm_password = (
                st.text_input(
                    "Confirm Password",
                    type="password"
                )
            )

            role = st.selectbox(
                "Role",
                [
                    "User",
                    "Admin"
                ]
            )

            st.markdown(
                "### Menu Permissions"
            )

            p_dashboard = st.checkbox(
                "Dashboard",
                value=True
            )

            p_instrument = st.checkbox(
                "Instrument Master"
            )

            p_item = st.checkbox(
                "Item Master"
            )

            p_stock_in = st.checkbox(
                "Stock IN"
            )

            p_stock_out = st.checkbox(
                "Stock OUT"
            )

            p_current = st.checkbox(
                "Current Stock"
            )

            p_reports = st.checkbox(
                "Reports"
            )

            p_transaction = (
                st.checkbox(
                    "Transaction Report"
                )
            )

            p_user_management = (
                st.checkbox(
                    "User Management"
                )
            )

            create_button = (
                st.form_submit_button(
                    "➕ Create User"
                )
            )

        if create_button:

            clean_username = (
                new_username.strip()
            )

            if not clean_username:

                st.warning(
                    "Enter Username."
                )

            elif (
                len(new_password)
                < 6
            ):

                st.warning(
                    "Password must be "
                    "at least 6 characters."
                )

            elif (
                new_password
                != confirm_password
            ):

                st.error(
                    "Passwords do not match."
                )

            else:

                check = (
                    supabase
                    .table("users")
                    .select("id")
                    .eq(
                        "username",
                        clean_username
                    )
                    .execute()
                )

                if check.data:

                    st.error(
                        "Username already exists."
                    )

                else:

                    (
                        supabase
                        .table("users")
                        .insert({
                            "username":
                                clean_username,

                            "password":
                                hash_password(
                                    new_password
                                ),

                            "role":
                                role,

                            "active":
                                1,

                            "can_dashboard":
                                int(
                                    p_dashboard
                                ),

                            "can_instrument":
                                int(
                                    p_instrument
                                ),

                            "can_item":
                                int(
                                    p_item
                                ),

                            "can_stock_in":
                                int(
                                    p_stock_in
                                ),

                            "can_stock_out":
                                int(
                                    p_stock_out
                                ),

                            "can_current_stock":
                                int(
                                    p_current
                                ),

                            "can_reports":
                                int(
                                    p_reports
                                ),

                            "can_transaction_report":
                                int(
                                    p_transaction
                                ),

                            "can_user_management":
                                int(
                                    p_user_management
                                )
                        })
                        .execute()
                    )

                    st.success(
                        "User created."
                    )

                    st.rerun()


    # =====================================================
    # MANAGE USER
    # =====================================================

    with tab2:

        response = (
            supabase
            .table("users")
            .select("*")
            .order("username")
            .execute()
        )

        users_df = pd.DataFrame(
            response.data
        )

        if users_df.empty:

            st.info(
                "No Users available."
            )

        else:

            usernames = (
                users_df[
                    "username"
                ].tolist()
            )

            selected_user = (
                st.selectbox(
                    "Select User",
                    usernames
                )
            )

            row = (
                users_df[
                    users_df[
                        "username"
                    ] == selected_user
                ]
                .iloc[0]
            )

            role_options = [
                "User",
                "Admin"
            ]

            current_role = (
                row["role"]
            )

            if (
                current_role
                not in role_options
            ):

                current_role = "User"

            selected_role = (
                st.selectbox(
                    "Role",
                    role_options,
                    index=(
                        role_options
                        .index(
                            current_role
                        )
                    )
                )
            )

            active_status = (
                st.checkbox(
                    "Active User",
                    value=bool(
                        row["active"]
                    )
                )
            )

            new_password = (
                st.text_input(
                    "New Password",
                    type="password",
                    help=(
                        "Leave blank to keep "
                        "current password."
                    )
                )
            )

            st.markdown(
                "### Menu Permissions"
            )

            p_dashboard = st.checkbox(
                "Dashboard",
                value=bool(
                    row[
                        "can_dashboard"
                    ]
                ),
                key="manage_dashboard"
            )

            p_instrument = st.checkbox(
                "Instrument Master",
                value=bool(
                    row[
                        "can_instrument"
                    ]
                ),
                key="manage_inst"
            )

            p_item = st.checkbox(
                "Item Master",
                value=bool(
                    row[
                        "can_item"
                    ]
                ),
                key="manage_item"
            )

            p_stock_in = st.checkbox(
                "Stock IN",
                value=bool(
                    row[
                        "can_stock_in"
                    ]
                ),
                key="manage_in"
            )

            p_stock_out = st.checkbox(
                "Stock OUT",
                value=bool(
                    row[
                        "can_stock_out"
                    ]
                ),
                key="manage_out"
            )

            p_current = st.checkbox(
                "Current Stock",
                value=bool(
                    row[
                        "can_current_stock"
                    ]
                ),
                key="manage_current"
            )

            p_reports = st.checkbox(
                "Reports",
                value=bool(
                    row[
                        "can_reports"
                    ]
                ),
                key="manage_reports"
            )

            p_transaction = st.checkbox(
                "Transaction Report",
                value=bool(
                    row[
                        "can_transaction_report"
                    ]
                ),
                key="manage_transaction"
            )

            p_user_management = (
                st.checkbox(
                    "User Management",
                    value=bool(
                        row[
                            "can_user_management"
                        ]
                    ),
                    key="manage_users"
                )
            )

            c1, c2 = st.columns(2)

            with c1:

                if st.button(
                    "💾 Update User"
                ):

                    if (
                        selected_user
                        ==
                        st.session_state
                        .username
                        and
                        not active_status
                    ):

                        st.error(
                            "You cannot deactivate "
                            "your own login."
                        )

                    elif (
                        new_password
                        and
                        len(new_password) < 6
                    ):

                        st.error(
                            "Password must be "
                            "at least 6 characters."
                        )

                    else:

                        update_data = {
                            "role":
                                selected_role,

                            "active":
                                int(
                                    active_status
                                ),

                            "can_dashboard":
                                int(
                                    p_dashboard
                                ),

                            "can_instrument":
                                int(
                                    p_instrument
                                ),

                            "can_item":
                                int(
                                    p_item
                                ),

                            "can_stock_in":
                                int(
                                    p_stock_in
                                ),

                            "can_stock_out":
                                int(
                                    p_stock_out
                                ),

                            "can_current_stock":
                                int(
                                    p_current
                                ),

                            "can_reports":
                                int(
                                    p_reports
                                ),

                            "can_transaction_report":
                                int(
                                    p_transaction
                                ),

                            "can_user_management":
                                int(
                                    p_user_management
                                )
                        }

                        if new_password:

                            update_data[
                                "password"
                            ] = (
                                hash_password(
                                    new_password
                                )
                            )

                        (
                            supabase
                            .table("users")
                            .update(
                                update_data
                            )
                            .eq(
                                "username",
                                selected_user
                            )
                            .execute()
                        )

                        st.success(
                            "User updated."
                        )

                        # force fresh permissions
                        if (
                            selected_user
                            ==
                            st.session_state
                            .username
                        ):

                            st.session_state.logged_in = False

                            st.warning(
                                "Please login again."
                            )

                        st.rerun()


            with c2:

                confirm_delete = (
                    st.checkbox(
                        "Confirm Delete User",
                        key="delete_user_confirm"
                    )
                )

                if st.button(
                    "🗑 Delete User"
                ):

                    if not confirm_delete:

                        st.warning(
                            "Tick Confirm Delete."
                        )

                    elif (
                        selected_user
                        ==
                        st.session_state
                        .username
                    ):

                        st.error(
                            "You cannot delete "
                            "your own login."
                        )

                    elif (
                        selected_user
                        == "admin"
                    ):

                        st.error(
                            "Default admin "
                            "cannot be deleted."
                        )

                    else:

                        (
                            supabase
                            .table("users")
                            .delete()
                            .eq(
                                "username",
                                selected_user
                            )
                            .execute()
                        )

                        st.success(
                            "User deleted."
                        )

                        st.rerun()


    # =====================================================
    # USER LIST
    # =====================================================

    st.divider()

    st.subheader(
        "User List"
    )

    response = (
        supabase
        .table("users")
        .select(
            "username,"
            "role,"
            "active,"
            "can_dashboard,"
            "can_instrument,"
            "can_item,"
            "can_stock_in,"
            "can_stock_out,"
            "can_current_stock,"
            "can_reports,"
            "can_transaction_report,"
            "can_user_management"
        )
        .order("username")
        .execute()
    )

    user_list = pd.DataFrame(
        response.data
    )

    if not user_list.empty:

        user_list["active"] = (
            user_list[
                "active"
            ].apply(
                lambda x:
                    "Active"
                    if int(x) == 1
                    else "Inactive"
            )
        )

        user_list = (
            user_list.rename(
                columns={
                    "username":
                        "Username",
                    "role":
                        "Role",
                    "active":
                        "Status",
                    "can_dashboard":
                        "Dashboard",
                    "can_instrument":
                        "Instrument",
                    "can_item":
                        "Item",
                    "can_stock_in":
                        "Stock IN",
                    "can_stock_out":
                        "Stock OUT",
                    "can_current_stock":
                        "Current Stock",
                    "can_reports":
                        "Reports",
                    "can_transaction_report":
                        "Transaction Report",
                    "can_user_management":
                        "User Management"
                }
            )
        )

    st.dataframe(
        user_list,
        width="stretch",
        hide_index=True
    )
