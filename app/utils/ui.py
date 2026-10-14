"""Streamlit helpers shared by all pages: session, guards, errors, tables."""

import logging
import time
from datetime import date

import pandas as pd
import streamlit as st

import config
from services import auth_service
from services.auth_service import AuthError
from utils.formatting import from_minor, label
from utils.permissions import PermissionDenied, has_permission
from utils.validators import ValidationError

log = logging.getLogger("meditrack")

EXPECTED_ERRORS = (ValidationError, PermissionDenied, AuthError)


# --- session ---------------------------------------------------------------

def login(user: dict) -> None:
    st.session_state["user_id"] = user["user_id"]
    st.session_state["last_activity"] = time.time()


def logout() -> None:
    user = current_user(touch=False)
    if user:
        try:
            auth_service.log_logout(user)
        except Exception:  # logging out must never fail
            log.exception("logout audit failed")
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def current_user(touch: bool = True) -> dict | None:
    """Reload the user from the database on every run so deactivation and role
    changes apply immediately; enforce the idle timeout."""
    user_id = st.session_state.get("user_id")
    if not user_id:
        return None
    idle = time.time() - st.session_state.get("last_activity", 0)
    if idle > config.SESSION_TIMEOUT_MINUTES * 60:
        st.session_state.clear()
        st.session_state["flash"] = ("warning", "Your session expired. Please log in again.")
        return None
    user = auth_service.load_user(user_id)
    if user is None or not user["active"]:
        st.session_state.clear()
        st.session_state["flash"] = ("error", "Your account is no longer active.")
        return None
    if touch:
        st.session_state["last_activity"] = time.time()
    return user


def require_page(permission: str) -> dict:
    """Top of every page: the page is shown only to logged-in users with the
    permission, even if reached by direct URL."""
    user = current_user()
    if user is None:
        st.warning("Please log in.")
        st.stop()
    if not has_permission(user, permission):
        st.error("You do not have permission to view this page.")
        st.stop()
    return user


def can(user, permission: str) -> bool:
    return has_permission(user, permission)


# --- feedback --------------------------------------------------------------

def flash(kind: str, message: str) -> None:
    """Show a message on the next run (survives st.rerun)."""
    st.session_state["flash"] = (kind, message)


def show_flash() -> None:
    item = st.session_state.pop("flash", None)
    if item:
        kind, message = item
        getattr(st, kind)(message)


def run_action(fn, *args, success: str | None = None, rerun: bool = True, **kwargs):
    """Call a service; show friendly errors. Returns the result or None."""
    try:
        result = fn(*args, **kwargs)
    except EXPECTED_ERRORS as exc:
        st.error(str(exc))
        return None
    except Exception:
        log.exception("Unexpected error in %s", getattr(fn, "__name__", fn))
        st.error("Something went wrong while saving. No changes were made. "
                 "Please try again or contact the administrator.")
        return None
    if success:
        flash("success", success)
    if rerun:
        st.rerun()
    return result


# --- tables ----------------------------------------------------------------

def frame(rows: list[dict], columns: dict[str, str] | None = None,
          money_cols: tuple[str, ...] = (), code_cols: tuple[str, ...] = ()) -> pd.DataFrame:
    """Rows -> DataFrame with readable headers. ``columns`` maps source -> label."""
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=list((columns or {}).values()))
    for col in money_cols:
        if col in df:
            df[col] = df[col].map(lambda m: float(from_minor(m)) if pd.notna(m) else None)
    for col in code_cols:
        if col in df:
            df[col] = df[col].map(label)
    if columns:
        df = df[[c for c in columns if c in df]].rename(columns=columns)
    return df


def table(df: pd.DataFrame, empty: str = "No records found.", money: tuple[str, ...] = (),
          height: int | None = None, **kwargs) -> None:
    if df.empty:
        st.info(empty)
        return
    cfg = {c: st.column_config.NumberColumn(c, format=f"{config.CURRENCY_SYMBOL}%.2f")
           for c in money if c in df}
    opts = {"hide_index": True, "width": "stretch", "column_config": cfg, **kwargs}
    if height:
        opts["height"] = height
    st.dataframe(df, **opts)


def option_map(rows: list[dict], key: str, fmt) -> dict:
    """{id: label} for select boxes: show labels, save ids."""
    return {r[key]: fmt(r) for r in rows}


def select_id(label_text: str, options: dict, *, key: str | None = None,
              placeholder: str = "Select...", **kwargs):
    if not options:
        st.selectbox(label_text, [], placeholder="Nothing available", disabled=True, key=key)
        return None
    return st.selectbox(label_text, list(options), format_func=lambda i: options[i],
                        index=None, placeholder=placeholder, key=key, **kwargs)


def date_range(prefix: str, default_days: int = 30, future_days: int = 0) -> tuple[date, date]:
    from datetime import timedelta
    from utils import clock
    today = clock.today()
    c1, c2 = st.columns(2)
    start = c1.date_input("From", today - timedelta(days=default_days), key=f"{prefix}_from")
    end = c2.date_input("To", today + timedelta(days=future_days), key=f"{prefix}_to")
    if start > end:
        st.warning("'From' is after 'To'; the dates were swapped.")
        start, end = end, start
    return start, end
