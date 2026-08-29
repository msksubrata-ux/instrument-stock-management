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

def get_user_allowed_instruments(username):

    # Admin সব Instrument দেখতে পারবে
    if st.session_state.role == "Admin":
        return get_instruments()

    response = (
        supabase
        .table("user_instrument_permissions")
        .select("instrument_name")
        .eq("username", username)
        .eq("can_stock_out", 1)
        .execute()
    )

    return [
        row["instrument_name"]
        for row in (response.data or [])
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

    st.header("📥 Stock IN")

    # =====================================================
    # EDIT / DELETE PERMISSION
    # =====================================================

    permission_check = (
        supabase
        .table("users")
        .select("can_stock_in_edit_delete")
        .eq(
            "username",
            st.session_state.username
        )
        .limit(1)
        .execute()
    )

    can_edit_delete = (
        st.session_state.role == "Admin"
    )

    if (
        not can_edit_delete
        and permission_check.data
    ):
        can_edit_delete = bool(
            permission_check.data[0].get(
                "can_stock_in_edit_delete",
                0
            )
        )


    # =====================================================
    # TABS
    # =====================================================

    if st.session_state.role == "Admin":

        tab_entry, tab_edit, tab_permission = st.tabs(
            [
                "➕ Stock IN Entry",
                "✏️ Edit / Delete",
                "🔐 Edit/Delete Permission"
            ]
        )

    elif can_edit_delete:

        tab_entry, tab_edit = st.tabs(
            [
                "➕ Stock IN Entry",
                "✏️ Edit / Delete"
            ]
        )

        tab_permission = None

    else:

        tab_entry = st.container()
        tab_edit = None
        tab_permission = None


    # =====================================================
    # STOCK IN ENTRY
    # =====================================================

    with tab_entry:

        instruments = get_instruments()

        if not instruments:

            st.warning(
                "No Instrument available."
            )

        else:

            # ---------------------------------------------
            # RESET AFTER SAVE
            # ---------------------------------------------

            if st.session_state.pop(
                "reset_stock_in",
                False
            ):

                st.session_state[
                    "stock_in_instrument"
                ] = "-- Select Instrument --"

                st.session_state[
                    "stock_in_item"
                ] = "-- Select Item --"

                st.session_state[
                    "stock_in_qty"
                ] = ""

                st.session_state[
                    "stock_in_rate"
                ] = ""

                st.session_state[
                    "stock_in_remarks"
                ] = ""


            # ---------------------------------------------
            # INSTRUMENT
            # ---------------------------------------------

            instrument_options = (
                ["-- Select Instrument --"]
                + instruments
            )

            instrument = st.selectbox(
                "Instrument",
                instrument_options,
                key="stock_in_instrument"
            )


            if (
                instrument
                == "-- Select Instrument --"
            ):

                st.info(
                    "Please select an Instrument."
                )

            else:

                # -----------------------------------------
                # ITEM
                # -----------------------------------------

                items = get_items(
                    instrument
                )

                if not items:

                    st.warning(
                        "No Item available."
                    )

                else:

                    item_options = (
                        ["-- Select Item --"]
                        + items
                    )

                    item = st.selectbox(
                        "Item",
                        item_options,
                        key="stock_in_item"
                    )


                    if (
                        item
                        == "-- Select Item --"
                    ):

                        st.info(
                            "Please select an Item."
                        )

                    else:

                        # ---------------------------------
                        # MASTER ITEM TYPE
                        # ---------------------------------

                        details = (
                            get_item_details(
                                instrument,
                                item
                            )
                        )

                        master_item_type = ""

                        if details:

                            master_item_type = (
                                details.get(
                                    "item_type",
                                    ""
                                )
                                or ""
                            )


                        # Item Type can also be typed
                        item_type = st.text_input(
                            "Item Type",
                            value=master_item_type,
                            key=(
                                f"stock_in_item_type_"
                                f"{instrument}_{item}"
                            )
                        )


                        # ---------------------------------
                        # CURRENT STOCK
                        # ---------------------------------

                        current_stock = (
                            get_current_stock(
                                instrument,
                                item
                            )
                        )

                        st.metric(
                            "Current Stock",
                            current_stock
                        )


                        # ---------------------------------
                        # QUANTITY
                        # ---------------------------------

                        quantity_text = (
                            st.text_input(
                                "Quantity",
                                key="stock_in_qty",
                                placeholder=(
                                    "Type quantity"
                                )
                            )
                        )


                        # ---------------------------------
                        # RATE
                        # ---------------------------------

                        rate_text = (
                            st.text_input(
                                "Rate (₹)",
                                key="stock_in_rate",
                                placeholder=(
                                    "Type rate"
                                )
                            )
                        )


                        quantity = 0.0
                        rate = 0.0
                        input_ok = True


                        # ---------------------------------
                        # QUANTITY VALIDATION
                        # ---------------------------------

                        if quantity_text.strip():

                            try:

                                quantity = float(
                                    quantity_text
                                    .replace(",", "")
                                    .strip()
                                )

                                if quantity <= 0:

                                    input_ok = False

                                    st.warning(
                                        "Quantity must be "
                                        "greater than 0."
                                    )

                            except ValueError:

                                input_ok = False

                                st.warning(
                                    "Quantity must be numeric."
                                )


                        # ---------------------------------
                        # RATE VALIDATION
                        # ---------------------------------

                        if rate_text.strip():

                            try:

                                rate = float(
                                    rate_text
                                    .replace(",", "")
                                    .strip()
                                )

                                if rate < 0:

                                    input_ok = False

                                    st.warning(
                                        "Rate cannot be negative."
                                    )

                            except ValueError:

                                input_ok = False

                                st.warning(
                                    "Rate must be numeric."
                                )


                        # ---------------------------------
                        # TOTAL VALUE
                        # ---------------------------------

                        if (
                            quantity_text.strip()
                            and rate_text.strip()
                            and input_ok
                        ):

                            total_value = (
                                quantity * rate
                            )

                            st.success(
                                f"Total Value: "
                                f"₹{total_value:,.2f}"
                            )


                        # ---------------------------------
                        # REMARKS
                        # ---------------------------------

                        remarks = st.text_input(
                            "Supplier / PO No. / Remarks",
                            key="stock_in_remarks"
                        )


                        # ---------------------------------
                        # SAVE
                        # ---------------------------------

                        if st.button(
                            "💾 Save Stock IN",
                            type="primary"
                        ):

                            if not item_type.strip():

                                st.warning(
                                    "Enter Item Type."
                                )

                            elif not quantity_text.strip():

                                st.warning(
                                    "Enter Quantity."
                                )

                            elif not rate_text.strip():

                                st.warning(
                                    "Enter Rate."
                                )

                            elif not input_ok:

                                pass

                            elif quantity <= 0:

                                st.warning(
                                    "Quantity must be "
                                    "greater than 0."
                                )

                            elif rate < 0:

                                st.warning(
                                    "Rate cannot be negative."
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
                                            item_type.strip(),

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

                                st.session_state[
                                    "reset_stock_in"
                                ] = True

                                st.rerun()


       # =====================================================
    # STOCK IN EDIT / DELETE
    # =====================================================

    if tab_edit is not None:

        with tab_edit:

            st.subheader("🔎 Find Stock IN Transaction")

            # ---------------------------------------------
            # LOAD STOCK IN TRANSACTIONS
            # ---------------------------------------------

            response = (
                supabase
                .table("transactions")
                .select(
                    "id,"
                    "txn_date,"
                    "instrument_name,"
                    "item_name,"
                    "item_type,"
                    "quantity,"
                    "rate,"
                    "remarks,"
                    "username"
                )
                .eq("txn_type", "IN")
                .order("id", desc=True)
                .execute()
            )

            stock_in_rows = response.data or []

            if not stock_in_rows:

                st.info(
                    "No Stock IN transactions available."
                )

            else:

                # =========================================
                # SEARCH / FILTER
                # =========================================

                filter_col1, filter_col2 = st.columns(2)

                with filter_col1:

                    search_in = st.text_input(
                        "🔎 Search",
                        placeholder=(
                            "Transaction ID / Instrument / "
                            "Item / Type / User"
                        ),
                        key="stock_in_search"
                    )

                    instrument_filter_in = st.selectbox(
                        "Filter by Instrument",
                        ["All"] + sorted(
                            list(
                                set(
                                    str(row.get(
                                        "instrument_name",
                                        ""
                                    ))
                                    for row in stock_in_rows
                                    if row.get(
                                        "instrument_name"
                                    )
                                )
                            )
                        ),
                        key="stock_in_filter_instrument"
                    )

                    item_filter_in = st.selectbox(
                        "Filter by Item",
                        ["All"] + sorted(
                            list(
                                set(
                                    str(row.get(
                                        "item_name",
                                        ""
                                    ))
                                    for row in stock_in_rows
                                    if row.get(
                                        "item_name"
                                    )
                                )
                            )
                        ),
                        key="stock_in_filter_item"
                    )

                with filter_col2:

                    type_filter_in = st.selectbox(
                        "Filter by Item Type",
                        ["All"] + sorted(
                            list(
                                set(
                                    str(row.get(
                                        "item_type",
                                        ""
                                    ))
                                    for row in stock_in_rows
                                    if row.get(
                                        "item_type"
                                    )
                                )
                            )
                        ),
                        key="stock_in_filter_type"
                    )

                    user_filter_in = st.selectbox(
                        "Filter by User",
                        ["All"] + sorted(
                            list(
                                set(
                                    str(row.get(
                                        "username",
                                        ""
                                    ))
                                    for row in stock_in_rows
                                    if row.get(
                                        "username"
                                    )
                                )
                            )
                        ),
                        key="stock_in_filter_user"
                    )


                # -----------------------------------------
                # GET MIN / MAX TRANSACTION DATE
                # -----------------------------------------

                valid_dates_in = []

                for row in stock_in_rows:

                    try:

                        date_value = str(
                            row.get(
                                "txn_date",
                                ""
                            )
                        )

                        parsed_date = (
                            datetime.fromisoformat(
                                date_value.replace(
                                    "Z",
                                    "+00:00"
                                )
                            ).date()
                        )

                        valid_dates_in.append(
                            parsed_date
                        )

                    except Exception:

                        pass


                if valid_dates_in:

                    min_date_in = min(
                        valid_dates_in
                    )

                    max_date_in = max(
                        valid_dates_in
                    )

                else:

                    min_date_in = (
                        datetime.now().date()
                    )

                    max_date_in = (
                        datetime.now().date()
                    )


                date_col1, date_col2 = st.columns(2)

                with date_col1:

                    from_date_in = st.date_input(
                        "From Date",
                        value=min_date_in,
                        key="stock_in_from_date"
                    )

                with date_col2:

                    to_date_in = st.date_input(
                        "To Date",
                        value=max_date_in,
                        key="stock_in_to_date"
                    )


                # =========================================
                # APPLY FILTERS
                # =========================================

                filtered_in_rows = []

                search_in_lower = (
                    search_in.strip().lower()
                )

                for row in stock_in_rows:

                    # -------------------------------------
                    # SEARCH TEXT
                    # -------------------------------------

                    searchable_text = (
                        f"{row.get('id', '')} "
                        f"{row.get('instrument_name', '')} "
                        f"{row.get('item_name', '')} "
                        f"{row.get('item_type', '')} "
                        f"{row.get('username', '')} "
                        f"{row.get('remarks', '')}"
                    ).lower()


                    if (
                        search_in_lower
                        and search_in_lower
                        not in searchable_text
                    ):

                        continue


                    # -------------------------------------
                    # INSTRUMENT FILTER
                    # -------------------------------------

                    if (
                        instrument_filter_in
                        != "All"
                        and row.get(
                            "instrument_name"
                        )
                        != instrument_filter_in
                    ):

                        continue


                    # -------------------------------------
                    # ITEM FILTER
                    # -------------------------------------

                    if (
                        item_filter_in
                        != "All"
                        and row.get(
                            "item_name"
                        )
                        != item_filter_in
                    ):

                        continue


                    # -------------------------------------
                    # ITEM TYPE FILTER
                    # -------------------------------------

                    if (
                        type_filter_in
                        != "All"
                        and row.get(
                            "item_type"
                        )
                        != type_filter_in
                    ):

                        continue


                    # -------------------------------------
                    # USER FILTER
                    # -------------------------------------

                    if (
                        user_filter_in
                        != "All"
                        and row.get(
                            "username"
                        )
                        != user_filter_in
                    ):

                        continue


                    # -------------------------------------
                    # DATE FILTER
                    # -------------------------------------

                    try:

                        row_date = (
                            datetime.fromisoformat(
                                str(
                                    row.get(
                                        "txn_date",
                                        ""
                                    )
                                ).replace(
                                    "Z",
                                    "+00:00"
                                )
                            ).date()
                        )

                        if (
                            row_date < from_date_in
                            or row_date > to_date_in
                        ):

                            continue

                    except Exception:

                        pass


                    filtered_in_rows.append(
                        row
                    )


                # =========================================
                # RESULT COUNT
                # =========================================

                st.info(
                    f"Found "
                    f"{len(filtered_in_rows)} "
                    f"Stock IN transaction(s)"
                )


                # =========================================
                # RESULT TABLE
                # =========================================

                if filtered_in_rows:

                    table_data_in = []

                    for row in filtered_in_rows:

                        try:

                            display_date = (
                                datetime.fromisoformat(
                                    str(
                                        row.get(
                                            "txn_date",
                                            ""
                                        )
                                    ).replace(
                                        "Z",
                                        "+00:00"
                                    )
                                ).strftime(
                                    "%d-%m-%Y"
                                )
                            )

                        except Exception:

                            display_date = str(
                                row.get(
                                    "txn_date",
                                    ""
                                )
                            )[:10]


                        qty_value = float(
                            row.get(
                                "quantity",
                                0
                            )
                            or 0
                        )

                        rate_value = float(
                            row.get(
                                "rate",
                                0
                            )
                            or 0
                        )

                        table_data_in.append({

                            "ID":
                                row.get(
                                    "id"
                                ),

                            "Date":
                                display_date,

                            "Instrument":
                                row.get(
                                    "instrument_name",
                                    ""
                                ),

                            "Item":
                                row.get(
                                    "item_name",
                                    ""
                                ),

                            "Item Type":
                                row.get(
                                    "item_type",
                                    ""
                                ),

                            "Qty":
                                qty_value,

                            "Rate":
                                rate_value,

                            "Total":
                                qty_value
                                * rate_value,

                            "User":
                                row.get(
                                    "username",
                                    ""
                                )
                        })


                    st.dataframe(
                        table_data_in,
                        use_container_width=True,
                        hide_index=True
                    )


                    # =====================================
                    # SELECT TRANSACTION
                    # =====================================

                    row_map_in = {}

                    row_labels_in = [
                        "-- Select Transaction --"
                    ]


                    for row in filtered_in_rows:

                        try:

                            short_date_in = (
                                datetime.fromisoformat(
                                    str(
                                        row.get(
                                            "txn_date",
                                            ""
                                        )
                                    ).replace(
                                        "Z",
                                        "+00:00"
                                    )
                                ).strftime(
                                    "%d-%m-%Y"
                                )
                            )

                        except Exception:

                            short_date_in = ""


                        label_in = (
                            f"ID {row['id']} | "
                            f"{short_date_in} | "
                            f"{row['instrument_name']} | "
                            f"{row['item_name']} | "
                            f"Qty "
                            f"{float(row['quantity']):g}"
                        )

                        row_labels_in.append(
                            label_in
                        )

                        row_map_in[
                            label_in
                        ] = row


                    selected_label_in = (
                        st.selectbox(
                            "Select Transaction to Edit / Delete",
                            row_labels_in,
                            key=(
                                "stock_in_edit_"
                                "transaction_select"
                            )
                        )
                    )


                    # =====================================
                    # SHOW EDIT FORM ONLY AFTER SELECTION
                    # =====================================

                    if (
                        selected_label_in
                        != "-- Select Transaction --"
                    ):

                        selected_row = (
                            row_map_in[
                                selected_label_in
                            ]
                        )

                        row_id = (
                            selected_row[
                                "id"
                            ]
                        )

                        old_instrument = (
                            selected_row[
                                "instrument_name"
                            ]
                        )

                        old_item = (
                            selected_row[
                                "item_name"
                            ]
                        )

                        old_item_type = (
                            selected_row.get(
                                "item_type",
                                ""
                            )
                            or ""
                        )

                        old_quantity = float(
                            selected_row.get(
                                "quantity",
                                0
                            )
                            or 0
                        )

                        old_rate = float(
                            selected_row.get(
                                "rate",
                                0
                            )
                            or 0
                        )


                        st.markdown("---")

                        st.subheader(
                            f"✏️ Edit Stock IN - ID {row_id}"
                        )


                        # =================================
                        # INSTRUMENT
                        # =================================

                        edit_instruments = (
                            get_instruments()
                        )

                        if (
                            old_instrument
                            not in edit_instruments
                        ):

                            edit_instruments.append(
                                old_instrument
                            )


                        instrument_index = (
                            edit_instruments.index(
                                old_instrument
                            )
                        )


                        new_instrument = st.selectbox(
                            "Instrument",
                            edit_instruments,
                            index=instrument_index,
                            key=(
                                f"in_edit_instrument_"
                                f"{row_id}"
                            )
                        )


                        # =================================
                        # ITEM
                        # =================================

                        edit_items = get_items(
                            new_instrument
                        )

                        if (
                            new_instrument
                            == old_instrument
                            and old_item
                            not in edit_items
                        ):

                            edit_items.append(
                                old_item
                            )


                        if edit_items:

                            if (
                                new_instrument
                                == old_instrument
                                and old_item
                                in edit_items
                            ):

                                item_index = (
                                    edit_items.index(
                                        old_item
                                    )
                                )

                            else:

                                item_index = 0


                            new_item = st.selectbox(
                                "Item",
                                edit_items,
                                index=item_index,
                                key=(
                                    f"in_edit_item_"
                                    f"{row_id}_"
                                    f"{new_instrument}"
                                )
                            )

                        else:

                            new_item = None

                            st.error(
                                "No Item available "
                                "for this Instrument."
                            )


                        # =================================
                        # ITEM TYPE
                        # =================================

                        default_item_type = (
                            old_item_type
                        )


                        if (
                            new_item
                            and (
                                new_instrument
                                != old_instrument
                                or new_item
                                != old_item
                            )
                        ):

                            new_details = (
                                get_item_details(
                                    new_instrument,
                                    new_item
                                )
                            )

                            if new_details:

                                default_item_type = (
                                    new_details.get(
                                        "item_type",
                                        ""
                                    )
                                    or ""
                                )


                        new_item_type = (
                            st.text_input(
                                "Item Type",
                                value=(
                                    default_item_type
                                ),
                                key=(
                                    f"in_edit_type_"
                                    f"{row_id}_"
                                    f"{new_instrument}_"
                                    f"{new_item}"
                                )
                            )
                        )


                        # =================================
                        # QUANTITY
                        # =================================

                        edit_qty_text = (
                            st.text_input(
                                "Quantity",
                                value=str(
                                    old_quantity
                                ),
                                key=(
                                    f"in_edit_qty_"
                                    f"{row_id}"
                                )
                            )
                        )


                        # =================================
                        # RATE
                        # =================================

                        edit_rate_text = (
                            st.text_input(
                                "Rate (₹)",
                                value=str(
                                    old_rate
                                ),
                                key=(
                                    f"in_edit_rate_"
                                    f"{row_id}"
                                )
                            )
                        )


                        # =================================
                        # TOTAL VALUE
                        # =================================

                        try:

                            preview_qty = float(
                                edit_qty_text
                                .replace(",", "")
                                .strip()
                            )

                            preview_rate = float(
                                edit_rate_text
                                .replace(",", "")
                                .strip()
                            )

                            st.success(
                                f"Total Value: "
                                f"₹"
                                f"{preview_qty * preview_rate:,.2f}"
                            )

                        except ValueError:

                            pass


                        # =================================
                        # REMARKS
                        # =================================

                        edit_remarks = (
                            st.text_input(
                                (
                                    "Supplier / PO No. "
                                    "/ Remarks"
                                ),
                                value=(
                                    selected_row.get(
                                        "remarks",
                                        ""
                                    )
                                    or ""
                                ),
                                key=(
                                    f"in_edit_remarks_"
                                    f"{row_id}"
                                )
                            )
                        )


                        update_col_in, delete_col_in = (
                            st.columns(2)
                        )


                        # =================================
                        # UPDATE
                        # =================================

                        with update_col_in:

                            if st.button(
                                "💾 Update Stock IN",
                                type="primary",
                                key=(
                                    f"update_stock_in_"
                                    f"{row_id}"
                                )
                            ):

                                if not new_item:

                                    st.error(
                                        "Select Item."
                                    )

                                elif (
                                    not
                                    new_item_type
                                    .strip()
                                ):

                                    st.error(
                                        "Enter Item Type."
                                    )

                                else:

                                    try:

                                        new_qty = float(
                                            edit_qty_text
                                            .replace(
                                                ",",
                                                ""
                                            )
                                            .strip()
                                        )

                                        new_rate = float(
                                            edit_rate_text
                                            .replace(
                                                ",",
                                                ""
                                            )
                                            .strip()
                                        )

                                    except ValueError:

                                        st.error(
                                            "Quantity and "
                                            "Rate must be "
                                            "numeric."
                                        )

                                    else:

                                        if new_qty <= 0:

                                            st.error(
                                                "Quantity must "
                                                "be greater "
                                                "than 0."
                                            )

                                        elif new_rate < 0:

                                            st.error(
                                                "Rate cannot "
                                                "be negative."
                                            )

                                        else:

                                            old_current_stock = (
                                                get_current_stock(
                                                    old_instrument,
                                                    old_item
                                                )
                                            )


                                            if (
                                                new_instrument
                                                == old_instrument
                                                and new_item
                                                == old_item
                                            ):

                                                final_old_stock = (
                                                    old_current_stock
                                                    - old_quantity
                                                    + new_qty
                                                )

                                            else:

                                                final_old_stock = (
                                                    old_current_stock
                                                    - old_quantity
                                                )


                                            if (
                                                final_old_stock
                                                < 0
                                            ):

                                                st.error(
                                                    "Cannot update. "
                                                    "Existing Stock "
                                                    "OUT uses this "
                                                    "quantity."
                                                )

                                            else:

                                                (
                                                    supabase
                                                    .table(
                                                        "transactions"
                                                    )
                                                    .update({

                                                        "instrument_name":
                                                            new_instrument,

                                                        "item_name":
                                                            new_item,

                                                        "item_type":
                                                            new_item_type
                                                            .strip(),

                                                        "quantity":
                                                            new_qty,

                                                        "rate":
                                                            new_rate,

                                                        "remarks":
                                                            edit_remarks
                                                            .strip()
                                                    })
                                                    .eq(
                                                        "id",
                                                        row_id
                                                    )
                                                    .execute()
                                                )

                                                st.success(
                                                    "Stock IN "
                                                    "updated."
                                                )

                                                st.rerun()


                        # =================================
                        # DELETE
                        # =================================

                        with delete_col_in:

                            confirm_delete_in = (
                                st.checkbox(
                                    "Confirm Delete",
                                    key=(
                                        f"in_delete_confirm_"
                                        f"{row_id}"
                                    )
                                )
                            )

                            if st.button(
                                "🗑 Delete Stock IN",
                                key=(
                                    f"delete_stock_in_"
                                    f"{row_id}"
                                )
                            ):

                                if (
                                    not
                                    confirm_delete_in
                                ):

                                    st.warning(
                                        "Tick "
                                        "Confirm Delete."
                                    )

                                else:

                                    current_stock_old = (
                                        get_current_stock(
                                            old_instrument,
                                            old_item
                                        )
                                    )

                                    stock_after_delete = (
                                        current_stock_old
                                        - old_quantity
                                    )


                                    if (
                                        stock_after_delete
                                        < 0
                                    ):

                                        st.error(
                                            "Cannot delete. "
                                            "Stock OUT already "
                                            "uses this quantity."
                                        )

                                    else:

                                        (
                                            supabase
                                            .table(
                                                "transactions"
                                            )
                                            .delete()
                                            .eq(
                                                "id",
                                                row_id
                                            )
                                            .execute()
                                        )

                                        st.success(
                                            "Stock IN "
                                            "deleted."
                                        )

                                        st.rerun()

                else:

                    st.warning(
                        "No transaction found "
                        "for selected filters."
                    )

    # =====================================================
    # STOCK IN PERMISSION
    # =====================================================

    if tab_permission is not None:

        with tab_permission:

            st.subheader(
                "🔐 Stock IN Edit/Delete Permission"
            )

            users_response = (
                supabase
                .table("users")
                .select(
                    "username,"
                    "role,"
                    "can_stock_in_edit_delete"
                )
                .order("username")
                .execute()
            )

            normal_users = [
                row
                for row in users_response.data
                if row["username"]
                != st.session_state.username
            ]


            if not normal_users:

                st.info(
                    "No other Users available."
                )

            else:

                permission_usernames = [
                    row["username"]
                    for row in normal_users
                ]

                selected_permission_user = (
                    st.selectbox(
                        "Select User",
                        permission_usernames,
                        key=(
                            "stock_in_permission_user"
                        )
                    )
                )

                permission_row = next(
                    row
                    for row in normal_users
                    if row["username"]
                    == selected_permission_user
                )

                allow_edit_delete = st.checkbox(
                    "Allow Stock IN Edit/Delete",
                    value=bool(
                        permission_row.get(
                            "can_stock_in_edit_delete",
                            0
                        )
                    ),
                    key=(
                        "allow_stock_in_edit_delete"
                    )
                )

                if st.button(
                    "💾 Save Stock IN Permission"
                ):

                    (
                        supabase
                        .table("users")
                        .update({
                            "can_stock_in_edit_delete":
                                int(
                                    allow_edit_delete
                                )
                        })
                        .eq(
                            "username",
                            selected_permission_user
                        )
                        .execute()
                    )

                    st.success(
                        "Stock IN permission updated."
                    )

                    st.rerun()



# =========================================================
# STOCK OUT
# =========================================================

elif menu == "Stock OUT":

    st.header("📤 Stock OUT")


    # =====================================================
    # HELPER: LAST STOCK IN RATE
    # =====================================================

    def get_last_stock_in_rate(
        instrument_name,
        item_name
    ):

        response = (
            supabase
            .table("transactions")
            .select("rate")
            .eq("txn_type", "IN")
            .eq(
                "instrument_name",
                instrument_name
            )
            .eq(
                "item_name",
                item_name
            )
            .order("id", desc=True)
            .limit(1)
            .execute()
        )

        if response.data:

            return float(
                response.data[0].get(
                    "rate",
                    0
                )
                or 0
            )

        return 0.0


    # =====================================================
    # EDIT / DELETE PERMISSION
    # =====================================================

    permission_check_out = (
        supabase
        .table("users")
        .select(
            "can_stock_out_edit_delete"
        )
        .eq(
            "username",
            st.session_state.username
        )
        .limit(1)
        .execute()
    )

    can_edit_delete_out = (
        st.session_state.role
        == "Admin"
    )

    if (
        not can_edit_delete_out
        and permission_check_out.data
    ):

        can_edit_delete_out = bool(
            permission_check_out.data[0].get(
                "can_stock_out_edit_delete",
                0
            )
        )


    # =====================================================
    # TABS
    # =====================================================

    if (
        st.session_state.role
        == "Admin"
    ):

        (
            tab_entry_out,
            tab_edit_out,
            tab_permission_out
        ) = st.tabs(
            [
                "➕ Stock OUT Entry",
                "✏️ Edit / Delete",
                "🔐 Edit/Delete Permission"
            ]
        )

    elif can_edit_delete_out:

        (
            tab_entry_out,
            tab_edit_out
        ) = st.tabs(
            [
                "➕ Stock OUT Entry",
                "✏️ Edit / Delete"
            ]
        )

        tab_permission_out = None

    else:

        tab_entry_out = st.container()
        tab_edit_out = None
        tab_permission_out = None

    # =====================================================
    # STOCK OUT ENTRY
    # =====================================================

    with tab_entry_out:

        # =================================================
        # USER-WISE INSTRUMENT PERMISSION
        # =================================================

        if st.session_state.role == "Admin":

            instruments_out = get_instruments()

        else:

            instruments_out = get_user_allowed_instruments(
                st.session_state.username
            )


        # =================================================
        # NO PERMISSION / NO INSTRUMENT
        # =================================================

        if not instruments_out:

            if st.session_state.role == "Admin":

                st.warning(
                    "No Instrument available."
                )

            else:

                st.warning(
                    "You do not have permission "
                    "for any Instrument. "
                    "Please contact Admin."
                )

        else:

            # =============================================
            # RESET AFTER SAVE
            # =============================================

            if st.session_state.pop(
                "reset_stock_out",
                False
            ):

                st.session_state[
                    "stock_out_instrument"
                ] = "-- Select Instrument --"

                st.session_state[
                    "stock_out_item"
                ] = "-- Select Item --"

                st.session_state[
                    "stock_out_qty"
                ] = ""

                st.session_state[
                    "stock_out_remarks"
                ] = ""


            # =============================================
            # INSTRUMENT
            # =============================================

            instrument_options_out = (
                ["-- Select Instrument --"]
                + instruments_out
            )

            instrument_out = st.selectbox(
                "Instrument",
                instrument_options_out,
                key="stock_out_instrument"
            )


            if (
                instrument_out
                == "-- Select Instrument --"
            ):

                st.info(
                    "Please select an Instrument."
                )

            else:

                # =========================================
                # ITEM
                # =========================================

                items_out = get_items(
                    instrument_out
                )

                if not items_out:

                    st.warning(
                        "No Item available."
                    )

                else:

                    item_options_out = (
                        ["-- Select Item --"]
                        + items_out
                    )

                    item_out = st.selectbox(
                        "Item",
                        item_options_out,
                        key="stock_out_item"
                    )


                    if (
                        item_out
                        == "-- Select Item --"
                    ):

                        st.info(
                            "Please select an Item."
                        )

                    else:

                        # =================================
                        # ITEM TYPE
                        # =================================

                        details_out = get_item_details(
                            instrument_out,
                            item_out
                        )

                        master_item_type_out = ""

                        if details_out:

                            master_item_type_out = (
                                details_out.get(
                                    "item_type",
                                    ""
                                )
                                or ""
                            )


                        item_type_out = st.text_input(
                            "Item Type",
                            value=master_item_type_out,
                            key=(
                                f"stock_out_item_type_"
                                f"{instrument_out}_"
                                f"{item_out}"
                            )
                        )


                        # =================================
                        # AVAILABLE STOCK
                        # =================================

                        available_stock = (
                            get_current_stock(
                                instrument_out,
                                item_out
                            )
                        )

                        st.metric(
                            "Available Stock",
                            available_stock
                        )


                        # =================================
                        # QUANTITY
                        # =================================

                        quantity_out_text = (
                            st.text_input(
                                "Quantity",
                                key="stock_out_qty",
                                placeholder="Type quantity"
                            )
                        )

                        quantity_out = 0.0
                        input_out_ok = True

                        if quantity_out_text.strip():

                            try:

                                quantity_out = float(
                                    quantity_out_text
                                    .replace(",", "")
                                    .strip()
                                )

                                if quantity_out <= 0:

                                    input_out_ok = False

                                    st.warning(
                                        "Quantity must be "
                                        "greater than 0."
                                    )

                            except ValueError:

                                input_out_ok = False

                                st.warning(
                                    "Quantity must be numeric."
                                )


                        # =================================
                        # LAST STOCK IN RATE
                        # =================================

                        rate_out = (
                            get_last_stock_in_rate(
                                instrument_out,
                                item_out
                            )
                        )

                        st.text_input(
                            "Rate (₹)",
                            value=f"{rate_out:.2f}",
                            disabled=True,
                            key=(
                                f"stock_out_rate_display_"
                                f"{instrument_out}_"
                                f"{item_out}"
                            )
                        )


                        # =================================
                        # TOTAL VALUE
                        # =================================

                        if (
                            quantity_out_text.strip()
                            and input_out_ok
                        ):

                            total_out_value = (
                                quantity_out
                                * rate_out
                            )

                            st.success(
                                f"Total Value: "
                                f"₹{total_out_value:,.2f}"
                            )


                        # =================================
                        # REMARKS
                        # =================================

                        remarks_out = st.text_input(
                            (
                                "Issued To / Department "
                                "/ Remarks"
                            ),
                            key="stock_out_remarks"
                        )


                        # =================================
                        # SAVE
                        # =================================

                        if st.button(
                            "💾 Save Stock OUT",
                            type="primary"
                        ):

                            if not item_type_out.strip():

                                st.warning(
                                    "Enter Item Type."
                                )

                            elif not quantity_out_text.strip():

                                st.warning(
                                    "Enter Quantity."
                                )

                            elif not input_out_ok:

                                pass

                            elif quantity_out > available_stock:

                                st.error(
                                    f"Insufficient Stock. "
                                    f"Available: "
                                    f"{available_stock:g}"
                                )

                            elif rate_out <= 0:

                                st.error(
                                    "No valid Stock IN "
                                    "Rate found."
                                )

                            else:

                                # Final permission check
                                if (
                                    st.session_state.role
                                    != "Admin"
                                ):

                                    final_allowed = (
                                        get_user_allowed_instruments(
                                            st.session_state.username
                                        )
                                    )

                                    if (
                                        instrument_out
                                        not in final_allowed
                                    ):

                                        st.error(
                                            "You do not have "
                                            "permission for this "
                                            "Instrument."
                                        )

                                        st.stop()


                                (
                                    supabase
                                    .table("transactions")
                                    .insert(
                                        {
                                            "txn_date":
                                                datetime.now()
                                                .astimezone()
                                                .isoformat(),

                                            "instrument_name":
                                                instrument_out,

                                            "item_name":
                                                item_out,

                                            "item_type":
                                                item_type_out.strip(),

                                            "txn_type":
                                                "OUT",

                                            "quantity":
                                                quantity_out,

                                            "rate":
                                                rate_out,

                                            "remarks":
                                                remarks_out.strip(),

                                            "username":
                                                st.session_state
                                                .username
                                        }
                                    )
                                    .execute()
                                )

                                st.success(
                                    "Stock OUT saved."
                                )

                                st.session_state[
                                    "reset_stock_out"
                                ] = True

                                st.rerun()


       # =====================================================
    # STOCK OUT EDIT / DELETE
    # =====================================================

    if tab_edit_out is not None:

        with tab_edit_out:

            st.subheader(
                "🔎 Find Stock OUT Transaction"
            )

            # =================================================
            # LOAD STOCK OUT TRANSACTIONS
            # =================================================

            response_out = (
                supabase
                .table("transactions")
                .select(
                    "id,"
                    "txn_date,"
                    "instrument_name,"
                    "item_name,"
                    "item_type,"
                    "quantity,"
                    "rate,"
                    "remarks,"
                    "username"
                )
                .eq(
                    "txn_type",
                    "OUT"
                )
                .order(
                    "id",
                    desc=True
                )
                .execute()
            )

            stock_out_rows = (
                response_out.data
                or []
            )


            # =================================================
            # USER-WISE INSTRUMENT RESTRICTION
            # =================================================

            if st.session_state.role != "Admin":

                allowed_out_instruments = (
                    get_user_allowed_instruments(
                        st.session_state.username
                    )
                )

                stock_out_rows = [
                    row
                    for row in stock_out_rows
                    if row.get("instrument_name")
                    in allowed_out_instruments
                ]


            # =================================================
            # NO TRANSACTIONS
            # =================================================

            if not stock_out_rows:

                if st.session_state.role == "Admin":

                    st.info(
                        "No Stock OUT transactions available."
                    )

                else:

                    st.info(
                        "No Stock OUT transactions available "
                        "for your permitted Instrument(s)."
                    )

            else:

                # =============================================
                # SEARCH / FILTER
                # =============================================

                filter_col1_out, filter_col2_out = (
                    st.columns(2)
                )


                with filter_col1_out:

                    search_out = st.text_input(
                        "🔎 Search",
                        placeholder=(
                            "Transaction ID / Instrument / "
                            "Item / Type / User"
                        ),
                        key="stock_out_search"
                    )


                    instrument_filter_out = st.selectbox(
                        "Filter by Instrument",
                        ["All"] + sorted(
                            list(
                                set(
                                    str(
                                        row.get(
                                            "instrument_name",
                                            ""
                                        )
                                    )
                                    for row
                                    in stock_out_rows
                                    if row.get(
                                        "instrument_name"
                                    )
                                )
                            )
                        ),
                        key=(
                            "stock_out_filter_instrument"
                        )
                    )


                    item_filter_out = st.selectbox(
                        "Filter by Item",
                        ["All"] + sorted(
                            list(
                                set(
                                    str(
                                        row.get(
                                            "item_name",
                                            ""
                                        )
                                    )
                                    for row
                                    in stock_out_rows
                                    if row.get(
                                        "item_name"
                                    )
                                )
                            )
                        ),
                        key=(
                            "stock_out_filter_item"
                        )
                    )


                with filter_col2_out:

                    type_filter_out = st.selectbox(
                        "Filter by Item Type",
                        ["All"] + sorted(
                            list(
                                set(
                                    str(
                                        row.get(
                                            "item_type",
                                            ""
                                        )
                                    )
                                    for row
                                    in stock_out_rows
                                    if row.get(
                                        "item_type"
                                    )
                                )
                            )
                        ),
                        key=(
                            "stock_out_filter_type"
                        )
                    )


                    user_filter_out = st.selectbox(
                        "Filter by User",
                        ["All"] + sorted(
                            list(
                                set(
                                    str(
                                        row.get(
                                            "username",
                                            ""
                                        )
                                    )
                                    for row
                                    in stock_out_rows
                                    if row.get(
                                        "username"
                                    )
                                )
                            )
                        ),
                        key=(
                            "stock_out_filter_user"
                        )
                    )


                # =============================================
                # DATE RANGE
                # =============================================

                valid_dates_out = []


                for row in stock_out_rows:

                    try:

                        parsed_date_out = (
                            datetime.fromisoformat(
                                str(
                                    row.get(
                                        "txn_date",
                                        ""
                                    )
                                ).replace(
                                    "Z",
                                    "+00:00"
                                )
                            ).date()
                        )

                        valid_dates_out.append(
                            parsed_date_out
                        )

                    except Exception:

                        pass


                if valid_dates_out:

                    min_date_out = min(
                        valid_dates_out
                    )

                    max_date_out = max(
                        valid_dates_out
                    )

                else:

                    min_date_out = (
                        datetime.now().date()
                    )

                    max_date_out = (
                        datetime.now().date()
                    )


                date_col1_out, date_col2_out = (
                    st.columns(2)
                )


                with date_col1_out:

                    from_date_out = st.date_input(
                        "From Date",
                        value=min_date_out,
                        key="stock_out_from_date"
                    )


                with date_col2_out:

                    to_date_out = st.date_input(
                        "To Date",
                        value=max_date_out,
                        key="stock_out_to_date"
                    )


                # =============================================
                # APPLY FILTERS
                # =============================================

                filtered_out_rows = []

                search_out_lower = (
                    search_out
                    .strip()
                    .lower()
                )


                for row in stock_out_rows:

                    searchable_out = (
                        f"{row.get('id', '')} "
                        f"{row.get('instrument_name', '')} "
                        f"{row.get('item_name', '')} "
                        f"{row.get('item_type', '')} "
                        f"{row.get('username', '')} "
                        f"{row.get('remarks', '')}"
                    ).lower()


                    # -----------------------------------------
                    # SEARCH
                    # -----------------------------------------

                    if (
                        search_out_lower
                        and search_out_lower
                        not in searchable_out
                    ):

                        continue


                    # -----------------------------------------
                    # INSTRUMENT
                    # -----------------------------------------

                    if (
                        instrument_filter_out
                        != "All"
                        and row.get(
                            "instrument_name"
                        )
                        != instrument_filter_out
                    ):

                        continue


                    # -----------------------------------------
                    # ITEM
                    # -----------------------------------------

                    if (
                        item_filter_out
                        != "All"
                        and row.get(
                            "item_name"
                        )
                        != item_filter_out
                    ):

                        continue


                    # -----------------------------------------
                    # ITEM TYPE
                    # -----------------------------------------

                    if (
                        type_filter_out
                        != "All"
                        and row.get(
                            "item_type"
                        )
                        != type_filter_out
                    ):

                        continue


                    # -----------------------------------------
                    # USER
                    # -----------------------------------------

                    if (
                        user_filter_out
                        != "All"
                        and row.get(
                            "username"
                        )
                        != user_filter_out
                    ):

                        continue


                    # -----------------------------------------
                    # DATE
                    # -----------------------------------------

                    try:

                        row_date_out = (
                            datetime.fromisoformat(
                                str(
                                    row.get(
                                        "txn_date",
                                        ""
                                    )
                                ).replace(
                                    "Z",
                                    "+00:00"
                                )
                            ).date()
                        )

                        if (
                            row_date_out
                            < from_date_out
                            or row_date_out
                            > to_date_out
                        ):

                            continue

                    except Exception:

                        pass


                    filtered_out_rows.append(
                        row
                    )


                # =============================================
                # RESULT COUNT
                # =============================================

                st.info(
                    f"Found "
                    f"{len(filtered_out_rows)} "
                    f"Stock OUT transaction(s)"
                )


                # =============================================
                # RESULTS
                # =============================================

                if filtered_out_rows:

                    table_data_out = []


                    for row in filtered_out_rows:

                        try:

                            display_date_out = (
                                datetime.fromisoformat(
                                    str(
                                        row.get(
                                            "txn_date",
                                            ""
                                        )
                                    ).replace(
                                        "Z",
                                        "+00:00"
                                    )
                                ).strftime(
                                    "%d-%m-%Y"
                                )
                            )

                        except Exception:

                            display_date_out = str(
                                row.get(
                                    "txn_date",
                                    ""
                                )
                            )[:10]


                        qty_value_out = float(
                            row.get(
                                "quantity",
                                0
                            )
                            or 0
                        )

                        rate_value_out = float(
                            row.get(
                                "rate",
                                0
                            )
                            or 0
                        )


                        table_data_out.append(
                            {
                                "ID":
                                    row.get(
                                        "id"
                                    ),

                                "Date":
                                    display_date_out,

                                "Instrument":
                                    row.get(
                                        "instrument_name",
                                        ""
                                    ),

                                "Item":
                                    row.get(
                                        "item_name",
                                        ""
                                    ),

                                "Item Type":
                                    row.get(
                                        "item_type",
                                        ""
                                    ),

                                "Qty":
                                    qty_value_out,

                                "Rate":
                                    rate_value_out,

                                "Total":
                                    qty_value_out
                                    * rate_value_out,

                                "User":
                                    row.get(
                                        "username",
                                        ""
                                    )
                            }
                        )


                    st.dataframe(
                        table_data_out,
                        use_container_width=True,
                        hide_index=True
                    )


                    # =========================================
                    # SELECT TRANSACTION
                    # =========================================

                    row_map_out = {}

                    row_labels_out = [
                        "-- Select Transaction --"
                    ]


                    for row in filtered_out_rows:

                        try:

                            short_date_out = (
                                datetime.fromisoformat(
                                    str(
                                        row.get(
                                            "txn_date",
                                            ""
                                        )
                                    ).replace(
                                        "Z",
                                        "+00:00"
                                    )
                                ).strftime(
                                    "%d-%m-%Y"
                                )
                            )

                        except Exception:

                            short_date_out = ""


                        label_out = (
                            f"ID {row['id']} | "
                            f"{short_date_out} | "
                            f"{row.get('instrument_name', '')} | "
                            f"{row.get('item_name', '')} | "
                            f"Qty "
                            f"{float(row.get('quantity', 0) or 0):g}"
                        )


                        row_labels_out.append(
                            label_out
                        )

                        row_map_out[
                            label_out
                        ] = row


                    selected_label_out = st.selectbox(
                        (
                            "Select Transaction "
                            "to Edit / Delete"
                        ),
                        row_labels_out,
                        key=(
                            "stock_out_edit_"
                            "transaction_select"
                        )
                    )


                    # =========================================
                    # EDIT FORM
                    # =========================================

                    if (
                        selected_label_out
                        != "-- Select Transaction --"
                    ):

                        selected_row_out = (
                            row_map_out[
                                selected_label_out
                            ]
                        )

                        row_id_out = (
                            selected_row_out[
                                "id"
                            ]
                        )

                        old_out_instrument = (
                            selected_row_out[
                                "instrument_name"
                            ]
                        )

                        old_out_item = (
                            selected_row_out[
                                "item_name"
                            ]
                        )

                        old_out_item_type = (
                            selected_row_out.get(
                                "item_type",
                                ""
                            )
                            or ""
                        )

                        old_out_quantity = float(
                            selected_row_out.get(
                                "quantity",
                                0
                            )
                            or 0
                        )


                        st.markdown("---")

                        st.subheader(
                            f"✏️ Edit Stock OUT - "
                            f"ID {row_id_out}"
                        )


                        # =====================================
                        # ALLOWED EDIT INSTRUMENTS
                        # =====================================

                        if (
                            st.session_state.role
                            == "Admin"
                        ):

                            out_edit_instruments = (
                                get_instruments()
                            )

                        else:

                            out_edit_instruments = (
                                get_user_allowed_instruments(
                                    st.session_state.username
                                )
                            )


                        # Safety:
                        # selected transaction should already
                        # belong to permitted instruments.

                        if (
                            old_out_instrument
                            not in out_edit_instruments
                        ):

                            st.error(
                                "You no longer have permission "
                                "for this Instrument."
                            )

                        else:

                            # =================================
                            # INSTRUMENT
                            # =================================

                            out_instrument_index = (
                                out_edit_instruments.index(
                                    old_out_instrument
                                )
                            )


                            new_out_instrument = st.selectbox(
                                "Instrument",
                                out_edit_instruments,
                                index=(
                                    out_instrument_index
                                ),
                                key=(
                                    f"out_edit_instrument_"
                                    f"{row_id_out}"
                                )
                            )


                            # =================================
                            # ITEM
                            # =================================

                            out_edit_items = get_items(
                                new_out_instrument
                            )


                            if (
                                new_out_instrument
                                == old_out_instrument
                                and old_out_item
                                not in out_edit_items
                            ):

                                out_edit_items.append(
                                    old_out_item
                                )


                            if out_edit_items:

                                if (
                                    new_out_instrument
                                    == old_out_instrument
                                    and old_out_item
                                    in out_edit_items
                                ):

                                    out_item_index = (
                                        out_edit_items.index(
                                            old_out_item
                                        )
                                    )

                                else:

                                    out_item_index = 0


                                new_out_item = st.selectbox(
                                    "Item",
                                    out_edit_items,
                                    index=out_item_index,
                                    key=(
                                        f"out_edit_item_"
                                        f"{row_id_out}_"
                                        f"{new_out_instrument}"
                                    )
                                )

                            else:

                                new_out_item = None

                                st.error(
                                    "No Item available "
                                    "for this Instrument."
                                )


                            # =================================
                            # ITEM TYPE
                            # =================================

                            default_out_type = (
                                old_out_item_type
                            )


                            if (
                                new_out_item
                                and (
                                    new_out_instrument
                                    != old_out_instrument
                                    or new_out_item
                                    != old_out_item
                                )
                            ):

                                new_out_details = (
                                    get_item_details(
                                        new_out_instrument,
                                        new_out_item
                                    )
                                )

                                if new_out_details:

                                    default_out_type = (
                                        new_out_details.get(
                                            "item_type",
                                            ""
                                        )
                                        or ""
                                    )


                            new_out_item_type = (
                                st.text_input(
                                    "Item Type",
                                    value=(
                                        default_out_type
                                    ),
                                    key=(
                                        f"out_edit_type_"
                                        f"{row_id_out}_"
                                        f"{new_out_instrument}_"
                                        f"{new_out_item}"
                                    )
                                )
                            )


                            # =================================
                            # QUANTITY
                            # =================================

                            edit_out_qty_text = (
                                st.text_input(
                                    "Quantity",
                                    value=str(
                                        old_out_quantity
                                    ),
                                    key=(
                                        f"out_edit_qty_"
                                        f"{row_id_out}"
                                    )
                                )
                            )


                            # =================================
                            # LAST STOCK IN RATE
                            # =================================

                            new_out_rate = 0.0


                            if new_out_item:

                                new_out_rate = (
                                    get_last_stock_in_rate(
                                        new_out_instrument,
                                        new_out_item
                                    )
                                )


                            st.text_input(
                                "Rate (₹)",
                                value=(
                                    f"{new_out_rate:.2f}"
                                ),
                                disabled=True,
                                key=(
                                    f"out_edit_rate_display_"
                                    f"{row_id_out}_"
                                    f"{new_out_instrument}_"
                                    f"{new_out_item}"
                                )
                            )


                            if new_out_rate <= 0:

                                st.warning(
                                    "No valid Stock IN Rate "
                                    "found."
                                )


                            # =================================
                            # TOTAL VALUE
                            # =================================

                            try:

                                preview_out_qty = float(
                                    edit_out_qty_text
                                    .replace(",", "")
                                    .strip()
                                )

                                st.success(
                                    f"Total Value: "
                                    f"₹"
                                    f"{preview_out_qty * new_out_rate:,.2f}"
                                )

                            except ValueError:

                                pass


                            # =================================
                            # REMARKS
                            # =================================

                            edit_out_remarks = (
                                st.text_input(
                                    (
                                        "Issued To / "
                                        "Department / Remarks"
                                    ),
                                    value=(
                                        selected_row_out.get(
                                            "remarks",
                                            ""
                                        )
                                        or ""
                                    ),
                                    key=(
                                        f"out_edit_remarks_"
                                        f"{row_id_out}"
                                    )
                                )
                            )


                            update_col_out, delete_col_out = (
                                st.columns(2)
                            )


                            # =================================
                            # UPDATE
                            # =================================

                            with update_col_out:

                                if st.button(
                                    "💾 Update Stock OUT",
                                    type="primary",
                                    key=(
                                        f"update_stock_out_"
                                        f"{row_id_out}"
                                    )
                                ):

                                    # -------------------------
                                    # FINAL USER PERMISSION
                                    # -------------------------

                                    permission_ok_out = True


                                    if (
                                        st.session_state.role
                                        != "Admin"
                                    ):

                                        latest_allowed_out = (
                                            get_user_allowed_instruments(
                                                st.session_state.username
                                            )
                                        )

                                        if (
                                            new_out_instrument
                                            not in latest_allowed_out
                                        ):

                                            permission_ok_out = False


                                    if not permission_ok_out:

                                        st.error(
                                            "You do not have "
                                            "permission for this "
                                            "Instrument."
                                        )

                                    elif not new_out_item:

                                        st.error(
                                            "Select Item."
                                        )

                                    elif (
                                        not
                                        new_out_item_type
                                        .strip()
                                    ):

                                        st.error(
                                            "Enter Item Type."
                                        )

                                    elif new_out_rate <= 0:

                                        st.error(
                                            "No valid Stock IN "
                                            "Rate found."
                                        )

                                    else:

                                        try:

                                            new_out_qty = float(
                                                edit_out_qty_text
                                                .replace(
                                                    ",",
                                                    ""
                                                )
                                                .strip()
                                            )

                                        except ValueError:

                                            st.error(
                                                "Quantity must "
                                                "be numeric."
                                            )

                                        else:

                                            if (
                                                new_out_qty
                                                <= 0
                                            ):

                                                st.error(
                                                    "Quantity must "
                                                    "be greater "
                                                    "than 0."
                                                )

                                            else:

                                                # =================
                                                # AVAILABLE STOCK
                                                # =================

                                                if (
                                                    new_out_instrument
                                                    == old_out_instrument
                                                    and new_out_item
                                                    == old_out_item
                                                ):

                                                    available_for_update = (
                                                        get_current_stock(
                                                            old_out_instrument,
                                                            old_out_item
                                                        )
                                                        + old_out_quantity
                                                    )

                                                else:

                                                    available_for_update = (
                                                        get_current_stock(
                                                            new_out_instrument,
                                                            new_out_item
                                                        )
                                                    )


                                                if (
                                                    new_out_qty
                                                    > available_for_update
                                                ):

                                                    st.error(
                                                        "Insufficient "
                                                        "Stock. "
                                                        f"Maximum "
                                                        f"available: "
                                                        f"{available_for_update:g}"
                                                    )

                                                else:

                                                    (
                                                        supabase
                                                        .table(
                                                            "transactions"
                                                        )
                                                        .update(
                                                            {
                                                                "instrument_name":
                                                                    new_out_instrument,

                                                                "item_name":
                                                                    new_out_item,

                                                                "item_type":
                                                                    new_out_item_type
                                                                    .strip(),

                                                                "quantity":
                                                                    new_out_qty,

                                                                "rate":
                                                                    new_out_rate,

                                                                "remarks":
                                                                    edit_out_remarks
                                                                    .strip()
                                                            }
                                                        )
                                                        .eq(
                                                            "id",
                                                            row_id_out
                                                        )
                                                        .execute()
                                                    )

                                                    st.success(
                                                        "Stock OUT "
                                                        "updated."
                                                    )

                                                    st.rerun()


                            # =================================
                            # DELETE
                            # =================================

                            with delete_col_out:

                                confirm_delete_out = (
                                    st.checkbox(
                                        "Confirm Delete",
                                        key=(
                                            f"out_delete_confirm_"
                                            f"{row_id_out}"
                                        )
                                    )
                                )


                                if st.button(
                                    "🗑 Delete Stock OUT",
                                    key=(
                                        f"delete_stock_out_"
                                        f"{row_id_out}"
                                    )
                                ):

                                    # -------------------------
                                    # FINAL DELETE PERMISSION
                                    # -------------------------

                                    delete_permission_ok = True


                                    if (
                                        st.session_state.role
                                        != "Admin"
                                    ):

                                        latest_allowed_delete = (
                                            get_user_allowed_instruments(
                                                st.session_state.username
                                            )
                                        )

                                        if (
                                            old_out_instrument
                                            not in
                                            latest_allowed_delete
                                        ):

                                            delete_permission_ok = False


                                    if (
                                        not
                                        delete_permission_ok
                                    ):

                                        st.error(
                                            "You do not have "
                                            "permission for this "
                                            "Instrument."
                                        )

                                    elif (
                                        not
                                        confirm_delete_out
                                    ):

                                        st.warning(
                                            "Tick Confirm Delete."
                                        )

                                    else:

                                        (
                                            supabase
                                            .table(
                                                "transactions"
                                            )
                                            .delete()
                                            .eq(
                                                "id",
                                                row_id_out
                                            )
                                            .execute()
                                        )

                                        st.success(
                                            "Stock OUT deleted."
                                        )

                                        st.rerun()


                else:

                    st.warning(
                        "No transaction found "
                        "for selected filters."
                    )
    # =====================================================
    # STOCK OUT PERMISSION
    # =====================================================

    if tab_permission_out is not None:

        with tab_permission_out:

            st.subheader(
                "🔐 Stock OUT "
                "Edit/Delete Permission"
            )


            users_response_out = (
                supabase
                .table("users")
                .select(
                    "username,"
                    "role,"
                    "can_stock_out_edit_delete"
                )
                .order("username")
                .execute()
            )


            normal_users_out = [

                row

                for row
                in users_response_out.data

                if (
                    row["username"]
                    != st.session_state.username
                )
            ]


            if not normal_users_out:

                st.info(
                    "No other Users available."
                )

            else:

                permission_usernames_out = [

                    row["username"]

                    for row
                    in normal_users_out
                ]


                selected_permission_user_out = (
                    st.selectbox(
                        "Select User",
                        permission_usernames_out,
                        key=(
                            "stock_out_"
                            "permission_user"
                        )
                    )
                )


                permission_row_out = next(

                    row

                    for row
                    in normal_users_out

                    if (
                        row["username"]
                        ==
                        selected_permission_user_out
                    )
                )


                allow_out_edit_delete = (
                    st.checkbox(
                        (
                            "Allow Stock OUT "
                            "Edit/Delete"
                        ),
                        value=bool(
                            permission_row_out.get(
                                "can_stock_out_edit_delete",
                                0
                            )
                        ),
                        key=(
                            "allow_stock_out_"
                            "edit_delete"
                        )
                    )
                )


                if st.button(
                    "💾 Save Stock OUT Permission"
                ):

                    (
                        supabase
                        .table("users")
                        .update({

                            "can_stock_out_edit_delete":
                                int(
                                    allow_out_edit_delete
                                )
                        })
                        .eq(
                            "username",
                            selected_permission_user_out
                        )
                        .execute()
                    )


                    st.success(
                        "Stock OUT permission updated."
                    )

                    st.rerun()

    # =====================================================
    # USER-WISE INSTRUMENT PERMISSION
    # =====================================================

    if st.session_state.role == "Admin":

        st.markdown("---")

        st.subheader(
            "🎯 User-wise Instrument Permission"
        )

        st.info(
            "Select a User and assign the Instruments "
            "that the User is allowed to access."
        )


        # =================================================
        # LOAD NORMAL USERS
        # =================================================

        user_permission_response = (
            supabase
            .table("users")
            .select(
                "username,role"
            )
            .order(
                "username"
            )
            .execute()
        )


        user_permission_rows = (
            user_permission_response.data
            or []
        )


        normal_permission_users = [

            row

            for row
            in user_permission_rows

            if row.get("role")
            != "Admin"
        ]


        # =================================================
        # NO USER
        # =================================================

        if not normal_permission_users:

            st.info(
                "No normal User available."
            )


        else:

            # =============================================
            # USER LIST
            # =============================================

            permission_user_list = [

                row["username"]

                for row
                in normal_permission_users
            ]


            # =============================================
            # SELECT USER
            # =============================================

            selected_permission_user = (
                st.selectbox(
                    "Select User",
                    permission_user_list,
                    key=(
                        "user_management_"
                        "instrument_permission_user"
                    )
                )
            )


            # =============================================
            # LOAD ALL INSTRUMENTS
            # =============================================

            permission_all_instruments = (
                get_instruments()
            )


            # =============================================
            # LOAD EXISTING PERMISSIONS
            # =============================================

            existing_permission_response = (
                supabase
                .table(
                    "user_instrument_permissions"
                )
                .select(
                    "instrument_name,"
                    "can_stock_out"
                )
                .eq(
                    "username",
                    selected_permission_user
                )
                .execute()
            )


            existing_permission_rows = (
                existing_permission_response.data
                or []
            )


            existing_allowed_instruments = {

                row["instrument_name"]

                for row
                in existing_permission_rows

                if int(
                    row.get(
                        "can_stock_out",
                        0
                    )
                    or 0
                ) == 1
            }


            # =============================================
            # DISPLAY USER
            # =============================================

            st.markdown(
                f"### Instrument Permission for "
                f"{selected_permission_user}"
            )


            st.write(
                "Tick the Instruments that this "
                "User can access:"
            )


            # =============================================
            # SELECT ALL / CLEAR ALL
            # =============================================

            permission_col1, permission_col2 = (
                st.columns(2)
            )


            with permission_col1:

                if st.button(
                    "✅ Select All Instruments",
                    key=(
                        "permission_select_all_"
                        + selected_permission_user
                    )
                ):

                    for instrument_name in (
                        permission_all_instruments
                    ):

                        st.session_state[
                            (
                                "user_inst_permission_"
                                + selected_permission_user
                                + "_"
                                + instrument_name
                            )
                        ] = True

                    st.rerun()


            with permission_col2:

                if st.button(
                    "❌ Clear All Instruments",
                    key=(
                        "permission_clear_all_"
                        + selected_permission_user
                    )
                ):

                    for instrument_name in (
                        permission_all_instruments
                    ):

                        st.session_state[
                            (
                                "user_inst_permission_"
                                + selected_permission_user
                                + "_"
                                + instrument_name
                            )
                        ] = False

                    st.rerun()


            st.markdown("---")


            # =============================================
            # INSTRUMENT CHECKBOXES
            # =============================================

            selected_permission_instruments = []


            if not permission_all_instruments:

                st.warning(
                    "No Instrument available "
                    "in Instrument Master."
                )


            else:

                for instrument_name in (
                    permission_all_instruments
                ):

                    checkbox_key = (
                        "user_inst_permission_"
                        + selected_permission_user
                        + "_"
                        + instrument_name
                    )


                    # -------------------------------------
                    # SET DEFAULT VALUE ONLY FIRST TIME
                    # -------------------------------------

                    if (
                        checkbox_key
                        not in st.session_state
                    ):

                        st.session_state[
                            checkbox_key
                        ] = (
                            instrument_name
                            in
                            existing_allowed_instruments
                        )


                    allowed_instrument = (
                        st.checkbox(
                            instrument_name,
                            key=checkbox_key
                        )
                    )


                    if allowed_instrument:

                        selected_permission_instruments.append(
                            instrument_name
                        )


            # =============================================
            # PERMISSION SUMMARY
            # =============================================

            st.markdown("---")


            st.write(
                "Selected Instruments:"
            )


            if selected_permission_instruments:

                for permission_instrument in (
                    selected_permission_instruments
                ):

                    st.write(
                        "✅ "
                        + permission_instrument
                    )

            else:

                st.warning(
                    "No Instrument selected."
                )


            # =============================================
            # SAVE PERMISSION
            # =============================================

            if st.button(
                "💾 Save Instrument Permission",
                type="primary",
                key=(
                    "user_management_"
                    "save_instrument_permission"
                )
            ):

                try:

                    # =====================================
                    # DELETE OLD PERMISSIONS
                    # =====================================

                    (
                        supabase
                        .table(
                            "user_instrument_permissions"
                        )
                        .delete()
                        .eq(
                            "username",
                            selected_permission_user
                        )
                        .execute()
                    )


                    # =====================================
                    # INSERT NEW PERMISSIONS
                    # =====================================

                    if (
                        selected_permission_instruments
                    ):

                        permission_insert_data = [

                            {
                                "username":
                                    selected_permission_user,

                                "instrument_name":
                                    instrument_name,

                                "can_stock_out":
                                    1
                            }

                            for instrument_name
                            in
                            selected_permission_instruments
                        ]


                        (
                            supabase
                            .table(
                                "user_instrument_permissions"
                            )
                            .insert(
                                permission_insert_data
                            )
                            .execute()
                        )


                    # =====================================
                    # SUCCESS
                    # =====================================

                    st.success(
                        "✅ Instrument Permission "
                        "saved successfully for "
                        f"{selected_permission_user}."
                    )


                    st.rerun()


                except Exception as e:

                    st.error(
                        "Unable to save Instrument "
                        "Permission."
                    )

                    st.error(
                        str(e)
                    )

# =====================================================
# CURRENT STOCK
# =====================================================

elif menu == "Current Stock":

    st.header(
        "📦 Current Stock Report"
    )


    # =================================================
    # DATE RANGE
    # =================================================

    from_date, to_date = (
        date_range_controls(
            "current_stock"
        )
    )


    # =================================================
    # FILTER COLUMNS
    # =================================================

    c1, c2, c3 = st.columns(3)


    # =================================================
    # INSTRUMENT FILTER
    # USER-WISE INSTRUMENT PERMISSION
    # =================================================

    with c1:

        if st.session_state.role == "Admin":

            current_stock_instruments = (
                get_instruments()
            )

        else:

            current_stock_instruments = (
                get_user_allowed_instruments(
                    st.session_state.username
                )
            )


        instrument_filter = (
            st.selectbox(
                "Instrument",
                ["ALL"]
                + current_stock_instruments,
                key=(
                    "current_stock_"
                    "instrument_filter"
                )
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


    # =====================================================
    # USER-WISE ALLOWED INSTRUMENTS
    # =====================================================

    if st.session_state.role == "Admin":

        report_allowed_instruments = (
            get_instruments()
        )

    else:

        report_allowed_instruments = (
            get_user_allowed_instruments(
                st.session_state.username
            )
        )


    # =====================================================
    # REPORT TYPE
    # =====================================================

    report_name = st.selectbox(
        "Select Report",
        [
            "Instrument Wise Report",
            "Stock Wise Report",
            "User Wise Report"
        ],
        key="main_report_type"
    )


    # =====================================================
    # INSTRUMENT WISE REPORT
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


        # ---------------------------------------------
        # LOAD MASTER
        # ---------------------------------------------

        master = load_items_master()


        # ---------------------------------------------
        # USER-WISE MASTER RESTRICTION
        # ---------------------------------------------

        if (
            st.session_state.role
            != "Admin"
            and not master.empty
        ):

            master = master[
                master[
                    "instrument_name"
                ].isin(
                    report_allowed_instruments
                )
            ].copy()


        # ---------------------------------------------
        # ITEM LIST
        # ---------------------------------------------

        report_item_list = []

        if not master.empty:

            report_item_list = sorted(
                master[
                    "item_name"
                ]
                .dropna()
                .unique()
                .tolist()
            )


        # ---------------------------------------------
        # FILTERS
        # ---------------------------------------------

        c1, c2, c3 = (
            st.columns(3)
        )


        with c1:

            instrument_filter = (
                st.selectbox(
                    "Instrument",
                    ["ALL"]
                    + report_allowed_instruments,
                    key=(
                        "instrument_wise_"
                        "instrument_filter"
                    )
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
                    ],
                    key=(
                        "instrument_wise_"
                        "type_filter"
                    )
                )
            )


        with c3:

            item_filter = (
                st.selectbox(
                    "Item",
                    ["ALL"]
                    + report_item_list,
                    key=(
                        "instrument_wise_"
                        "item_filter"
                    )
                )
            )


        # ---------------------------------------------
        # LOAD TRANSACTIONS
        # ---------------------------------------------

        tx = load_transactions()


        # ---------------------------------------------
        # USER-WISE TRANSACTION RESTRICTION
        # ---------------------------------------------

        if (
            st.session_state.role
            != "Admin"
            and not tx.empty
        ):

            tx = tx[
                tx[
                    "instrument_name"
                ].isin(
                    report_allowed_instruments
                )
            ].copy()


        period_tx = filter_date_range(
            tx,
            from_date,
            to_date
        )


        # ---------------------------------------------
        # CREATE REPORT
        # ---------------------------------------------

        rows = []


        if not master.empty:

            for _, row in master.iterrows():

                inst = row[
                    "instrument_name"
                ]

                item = row[
                    "item_name"
                ]


                # -------------------------------------
                # EXTRA PERMISSION SAFETY
                # -------------------------------------

                if (
                    st.session_state.role
                    != "Admin"
                    and inst
                    not in report_allowed_instruments
                ):

                    continue


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


                total_in = 0.0
                total_out = 0.0


                if not item_tx.empty:

                    total_in = float(
                        item_tx.loc[
                            item_tx[
                                "txn_type"
                            ] == "IN",
                            "quantity"
                        ].sum()
                    )


                    total_out = float(
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


                rows.append(
                    {
                        "Instrument":
                            inst,

                        "Item":
                            item,

                        "Type":
                            row[
                                "item_type"
                            ],

                        "Unit":
                            row[
                                "unit"
                            ],

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
                    }
                )


        report_df = pd.DataFrame(
            rows
        )


        # ---------------------------------------------
        # APPLY DISPLAY FILTER
        # ---------------------------------------------

        if not report_df.empty:

            # Security restriction again
            report_df = report_df[
                report_df[
                    "Instrument"
                ].isin(
                    report_allowed_instruments
                )
            ].copy()


            if (
                instrument_filter
                != "ALL"
            ):

                report_df = report_df[
                    report_df[
                        "Instrument"
                    ]
                    == instrument_filter
                ]


            if (
                type_filter
                != "ALL"
            ):

                report_df = report_df[
                    report_df[
                        "Type"
                    ]
                    == type_filter
                ]


            if (
                item_filter
                != "ALL"
            ):

                report_df = report_df[
                    report_df[
                        "Item"
                    ]
                    == item_filter
                ]


        # ---------------------------------------------
        # SHOW REPORT
        # ---------------------------------------------

        st.dataframe(
            report_df,
            width="stretch",
            hide_index=True
        )


        csv = report_df.to_csv(
            index=False
        ).encode(
            "utf-8"
        )


        st.download_button(
            "⬇️ Download Instrument Wise Report",
            csv,
            "instrument_wise_report.csv",
            "text/csv"
        )


    # =====================================================
    # STOCK WISE REPORT
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


        # ---------------------------------------------
        # LOAD MASTER
        # ---------------------------------------------

        master = load_items_master()


        # ---------------------------------------------
        # USER-WISE MASTER RESTRICTION
        # ---------------------------------------------

        if (
            st.session_state.role
            != "Admin"
            and not master.empty
        ):

            master = master[
                master[
                    "instrument_name"
                ].isin(
                    report_allowed_instruments
                )
            ].copy()


        # ---------------------------------------------
        # ITEM LIST
        # ---------------------------------------------

        stock_report_item_list = []

        if not master.empty:

            stock_report_item_list = sorted(
                master[
                    "item_name"
                ]
                .dropna()
                .unique()
                .tolist()
            )


        # ---------------------------------------------
        # FILTERS
        # ---------------------------------------------

        c1, c2, c3 = (
            st.columns(3)
        )


        with c1:

            instrument_filter = (
                st.selectbox(
                    "Instrument",
                    ["ALL"]
                    + report_allowed_instruments,
                    key=(
                        "stock_wise_"
                        "instrument_filter"
                    )
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
                    ],
                    key=(
                        "stock_wise_"
                        "type_filter"
                    )
                )
            )


        with c3:

            item_filter = (
                st.selectbox(
                    "Item",
                    ["ALL"]
                    + stock_report_item_list,
                    key=(
                        "stock_wise_"
                        "item_filter"
                    )
                )
            )


        # ---------------------------------------------
        # TRANSACTIONS
        # ---------------------------------------------

        tx = load_transactions()


        if (
            st.session_state.role
            != "Admin"
            and not tx.empty
        ):

            tx = tx[
                tx[
                    "instrument_name"
                ].isin(
                    report_allowed_instruments
                )
            ].copy()


        period_tx = filter_date_range(
            tx,
            from_date,
            to_date
        )


        # ---------------------------------------------
        # CREATE REPORT
        # ---------------------------------------------

        rows = []


        if not master.empty:

            for _, row in master.iterrows():

                inst = row[
                    "instrument_name"
                ]

                item = row[
                    "item_name"
                ]


                if (
                    st.session_state.role
                    != "Admin"
                    and inst
                    not in report_allowed_instruments
                ):

                    continue


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


                total_in = 0.0
                total_out = 0.0


                if not item_tx.empty:

                    total_in = float(
                        item_tx.loc[
                            item_tx[
                                "txn_type"
                            ] == "IN",
                            "quantity"
                        ].sum()
                    )


                    total_out = float(
                        item_tx.loc[
                            item_tx[
                                "txn_type"
                            ] == "OUT",
                            "quantity"
                        ].sum()
                    )


                opening_date = (
                    from_date
                    - timedelta(
                        days=1
                    )
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
                    row[
                        "min_stock"
                    ]
                    or 0
                )


                status = (
                    "LOW STOCK"
                    if closing_stock
                    <= minimum
                    else "OK"
                )


                rows.append(
                    {
                        "Instrument":
                            inst,

                        "Item":
                            item,

                        "Type":
                            row[
                                "item_type"
                            ],

                        "Unit":
                            row[
                                "unit"
                            ],

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
                    }
                )


        report_df = pd.DataFrame(
            rows
        )


        # ---------------------------------------------
        # APPLY FILTER
        # ---------------------------------------------

        if not report_df.empty:

            # Permission restriction
            report_df = report_df[
                report_df[
                    "Instrument"
                ].isin(
                    report_allowed_instruments
                )
            ].copy()


            if (
                instrument_filter
                != "ALL"
            ):

                report_df = report_df[
                    report_df[
                        "Instrument"
                    ]
                    == instrument_filter
                ]


            if (
                type_filter
                != "ALL"
            ):

                report_df = report_df[
                    report_df[
                        "Type"
                    ]
                    == type_filter
                ]


            if (
                item_filter
                != "ALL"
            ):

                report_df = report_df[
                    report_df[
                        "Item"
                    ]
                    == item_filter
                ]


        # ---------------------------------------------
        # SHOW
        # ---------------------------------------------

        st.dataframe(
            report_df,
            width="stretch",
            hide_index=True
        )


        csv = report_df.to_csv(
            index=False
        ).encode(
            "utf-8"
        )


        st.download_button(
            "⬇️ Download Stock Wise Report",
            csv,
            "stock_wise_report.csv",
            "text/csv"
        )


    # =====================================================
    # USER WISE REPORT
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


        # ---------------------------------------------
        # LOAD TRANSACTIONS
        # ---------------------------------------------

        tx = load_transactions()


        # ---------------------------------------------
        # USER-WISE INSTRUMENT RESTRICTION
        # ---------------------------------------------

        if (
            st.session_state.role
            != "Admin"
            and not tx.empty
        ):

            tx = tx[
                tx[
                    "instrument_name"
                ].isin(
                    report_allowed_instruments
                )
            ].copy()


        filtered = filter_date_range(
            tx,
            from_date,
            to_date
        )


        # ---------------------------------------------
        # USERS
        # ---------------------------------------------

        usernames = []


        if not tx.empty:

            usernames = sorted(
                tx[
                    "username"
                ]
                .dropna()
                .unique()
                .tolist()
            )


        # ---------------------------------------------
        # FILTERS
        # ---------------------------------------------

        c1, c2 = (
            st.columns(2)
        )


        with c1:

            user_filter = (
                st.selectbox(
                    "User",
                    ["ALL"]
                    + usernames,
                    key=(
                        "user_wise_"
                        "user_filter"
                    )
                )
            )


        with c2:

            instrument_filter = (
                st.selectbox(
                    "Instrument",
                    ["ALL"]
                    + report_allowed_instruments,
                    key=(
                        "user_wise_"
                        "instrument_filter"
                    )
                )
            )


        c3, c4 = (
            st.columns(2)
        )


        with c3:

            type_filter = (
                st.selectbox(
                    "Item Type",
                    [
                        "ALL",
                        "Spare",
                        "Consumable"
                    ],
                    key=(
                        "user_wise_"
                        "type_filter"
                    )
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
                    ],
                    key=(
                        "user_wise_"
                        "transaction_filter"
                    )
                )
            )


        # ---------------------------------------------
        # APPLY FILTERS
        # ---------------------------------------------

        if not filtered.empty:

            # Permission restriction
            filtered = filtered[
                filtered[
                    "instrument_name"
                ].isin(
                    report_allowed_instruments
                )
            ].copy()


            if (
                user_filter
                != "ALL"
            ):

                filtered = filtered[
                    filtered[
                        "username"
                    ]
                    == user_filter
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


            if (
                type_filter
                != "ALL"
            ):

                filtered = filtered[
                    filtered[
                        "item_type"
                    ]
                    == type_filter
                ]


            if (
                txn_filter
                != "ALL"
            ):

                filtered = filtered[
                    filtered[
                        "txn_type"
                    ]
                    == txn_filter
                ]


        # ---------------------------------------------
        # DISPLAY DATAFRAME
        # ---------------------------------------------

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
        ).encode(
            "utf-8"
        )


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


    # =====================================================
    # USER-WISE INSTRUMENT PERMISSION
    # =====================================================

    if st.session_state.role == "Admin":

        transaction_allowed_instruments = (
            get_instruments()
        )

    else:

        transaction_allowed_instruments = (
            get_user_allowed_instruments(
                st.session_state.username
            )
        )


    # =====================================================
    # DATE RANGE
    # =====================================================

    from_date, to_date = (
        date_range_controls(
            "transaction_report"
        )
    )


    # =====================================================
    # LOAD TRANSACTIONS
    # =====================================================

    tx = load_transactions()


    # =====================================================
    # SECURITY - RESTRICT USER INSTRUMENTS
    # =====================================================

    if (
        st.session_state.role
        != "Admin"
        and not tx.empty
    ):

        tx = tx[
            tx[
                "instrument_name"
            ].isin(
                transaction_allowed_instruments
            )
        ].copy()


    # =====================================================
    # DATE FILTER
    # =====================================================

    filtered = filter_date_range(
        tx,
        from_date,
        to_date
    )


    # =====================================================
    # USER LIST
    # =====================================================

    usernames = []


    if not tx.empty:

        usernames = sorted(
            tx[
                "username"
            ]
            .dropna()
            .unique()
            .tolist()
        )


    # =====================================================
    # FILTER ROW 1
    # =====================================================

    c1, c2 = (
        st.columns(2)
    )


    with c1:

        instrument_filter = (
            st.selectbox(
                "Instrument",
                ["ALL"]
                + transaction_allowed_instruments,
                key=(
                    "transaction_report_"
                    "instrument_filter"
                )
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
                ],
                key=(
                    "transaction_report_"
                    "type_filter"
                )
            )
        )


    # =====================================================
    # FILTER ROW 2
    # =====================================================

    c3, c4 = (
        st.columns(2)
    )


    with c3:

        txn_filter = (
            st.selectbox(
                "Transaction Type",
                [
                    "ALL",
                    "IN",
                    "OUT"
                ],
                key=(
                    "transaction_report_"
                    "transaction_filter"
                )
            )
        )


    with c4:

        user_filter = (
            st.selectbox(
                "User",
                ["ALL"]
                + usernames,
                key=(
                    "transaction_report_"
                    "user_filter"
                )
            )
        )


    # =====================================================
    # APPLY FILTERS
    # =====================================================

    if not filtered.empty:

        # -------------------------------------------------
        # FINAL INSTRUMENT PERMISSION SECURITY
        # -------------------------------------------------

        filtered = filtered[
            filtered[
                "instrument_name"
            ].isin(
                transaction_allowed_instruments
            )
        ].copy()


        # -------------------------------------------------
        # INSTRUMENT
        # -------------------------------------------------

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


        # -------------------------------------------------
        # ITEM TYPE
        # -------------------------------------------------

        if (
            type_filter
            != "ALL"
        ):

            filtered = filtered[
                filtered[
                    "item_type"
                ]
                == type_filter
            ]


        # -------------------------------------------------
        # TRANSACTION TYPE
        # -------------------------------------------------

        if (
            txn_filter
            != "ALL"
        ):

            filtered = filtered[
                filtered[
                    "txn_type"
                ]
                == txn_filter
            ]


        # -------------------------------------------------
        # USER
        # -------------------------------------------------

        if (
            user_filter
            != "ALL"
        ):

            filtered = filtered[
                filtered[
                    "username"
                ]
                == user_filter
            ]


    # =====================================================
    # DISPLAY TABLE
    # =====================================================

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


    # =====================================================
    # DOWNLOAD
    # =====================================================

    csv = display_df.to_csv(
        index=False
    ).encode(
        "utf-8"
    )


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
    # =====================================================
    # USER-WISE INSTRUMENT PERMISSION
    # =====================================================

    if st.session_state.role == "Admin":

        st.markdown("---")

        st.subheader(
            "🎯 User-wise Instrument Permission"
        )

        st.info(
            "Select a User and assign the Instruments "
            "that the User is allowed to access."
        )

        # =================================================
        # LOAD NORMAL USERS
        # =================================================

        user_permission_response = (
            supabase
            .table("users")
            .select("username,role")
            .order("username")
            .execute()
        )

        user_permission_rows = (
            user_permission_response.data
            or []
        )

        normal_permission_users = [
            row
            for row in user_permission_rows
            if row.get("role") != "Admin"
        ]

        # =================================================
        # NO USER
        # =================================================

        if not normal_permission_users:

            st.info(
                "No normal User available."
            )

        else:

            # =============================================
            # USER LIST
            # =============================================

            permission_user_list = [
                row["username"]
                for row in normal_permission_users
            ]

            # =============================================
            # SELECT USER
            # =============================================

            selected_permission_user = (
                st.selectbox(
                    "Select User",
                    permission_user_list,
                    key=(
                        "user_management_"
                        "instrument_permission_user"
                    )
                )
            )

            # =============================================
            # LOAD ALL INSTRUMENTS
            # =============================================

            permission_all_instruments = (
                get_instruments()
            )

            # =============================================
            # LOAD EXISTING PERMISSIONS
            # =============================================

            existing_permission_response = (
                supabase
                .table(
                    "user_instrument_permissions"
                )
                .select(
                    "instrument_name,"
                    "can_stock_out"
                )
                .eq(
                    "username",
                    selected_permission_user
                )
                .execute()
            )

            existing_permission_rows = (
                existing_permission_response.data
                or []
            )

            existing_allowed_instruments = {
                row["instrument_name"]
                for row
                in existing_permission_rows
                if int(
                    row.get(
                        "can_stock_out",
                        0
                    )
                    or 0
                ) == 1
            }

            # =============================================
            # DISPLAY USER
            # =============================================

            st.markdown(
                f"### Instrument Permission for "
                f"{selected_permission_user}"
            )

            st.write(
                "Tick the Instruments that this "
                "User can access:"
            )

            # =============================================
            # SELECT ALL / CLEAR ALL
            # =============================================

            permission_col1, permission_col2 = (
                st.columns(2)
            )

            with permission_col1:

                if st.button(
                    "✅ Select All Instruments",
                    key=(
                        "permission_select_all_"
                        + selected_permission_user
                    )
                ):

                    for instrument_name in (
                        permission_all_instruments
                    ):

                        st.session_state[
                            (
                                "user_inst_permission_"
                                + selected_permission_user
                                + "_"
                                + instrument_name
                            )
                        ] = True

                    st.rerun()

            with permission_col2:

                if st.button(
                    "❌ Clear All Instruments",
                    key=(
                        "permission_clear_all_"
                        + selected_permission_user
                    )
                ):

                    for instrument_name in (
                        permission_all_instruments
                    ):

                        st.session_state[
                            (
                                "user_inst_permission_"
                                + selected_permission_user
                                + "_"
                                + instrument_name
                            )
                        ] = False

                    st.rerun()

            st.markdown("---")

            # =============================================
            # INSTRUMENT CHECKBOXES
            # =============================================

            selected_permission_instruments = []

            if not permission_all_instruments:

                st.warning(
                    "No Instrument available "
                    "in Instrument Master."
                )

            else:

                for instrument_name in (
                    permission_all_instruments
                ):

                    checkbox_key = (
                        "user_inst_permission_"
                        + selected_permission_user
                        + "_"
                        + instrument_name
                    )

                    if (
                        checkbox_key
                        not in st.session_state
                    ):

                        st.session_state[
                            checkbox_key
                        ] = (
                            instrument_name
                            in existing_allowed_instruments
                        )

                    allowed_instrument = (
                        st.checkbox(
                            instrument_name,
                            key=checkbox_key
                        )
                    )

                    if allowed_instrument:

                        selected_permission_instruments.append(
                            instrument_name
                        )

            # =============================================
            # SELECTED SUMMARY
            # =============================================

            st.markdown("---")

            st.write(
                "Selected Instruments:"
            )

            if selected_permission_instruments:

                for permission_instrument in (
                    selected_permission_instruments
                ):

                    st.write(
                        "✅ "
                        + permission_instrument
                    )

            else:

                st.warning(
                    "No Instrument selected."
                )

            # =============================================
            # SAVE PERMISSION
            # =============================================

            if st.button(
                "💾 Save Instrument Permission",
                type="primary",
                key=(
                    "user_management_"
                    "save_instrument_permission"
                )
            ):

                try:

                    # =====================================
                    # DELETE OLD PERMISSIONS
                    # =====================================

                    (
                        supabase
                        .table(
                            "user_instrument_permissions"
                        )
                        .delete()
                        .eq(
                            "username",
                            selected_permission_user
                        )
                        .execute()
                    )

                    # =====================================
                    # INSERT NEW PERMISSIONS
                    # =====================================

                    if selected_permission_instruments:

                        permission_insert_data = [
                            {
                                "username":
                                    selected_permission_user,

                                "instrument_name":
                                    instrument_name,

                                "can_stock_out":
                                    1
                            }

                            for instrument_name
                            in selected_permission_instruments
                        ]

                        (
                            supabase
                            .table(
                                "user_instrument_permissions"
                            )
                            .insert(
                                permission_insert_data
                            )
                            .execute()
                        )

                    st.success(
                        "✅ Instrument Permission saved "
                        f"successfully for "
                        f"{selected_permission_user}."
                    )

                    st.rerun()

                except Exception as e:

                    st.error(
                        "Unable to save Instrument "
                        "Permission."
                    )

                    st.error(
                        str(e)
                    )
