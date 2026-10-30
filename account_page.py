"""Account and plans view.

Reads the signed-in user and the commercial catalogue. Stock access stays
in access.py. Logout is the callback the rest of the app already uses.
"""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st

import accounts
import plans
from accounts import User

_LAYOUT = """
<style>
section.main [data-testid="stHorizontalBlock"] {
  flex-wrap: wrap;
}
section.main [data-testid="stHorizontalBlock"] > [data-testid="column"] {
  flex: 1 1 17rem !important;
  width: auto !important;
  min-width: min(100%, 17rem);
}
section.main [data-testid="stVerticalBlockBorderWrapper"]:has(.td-current) {
  border-color: #0284c7 !important;
  box-shadow: inset 0 0 0 1px #0284c7;
}
</style>
"""


def render_account(user: User, active_plan: str, logout: Callable[[], None]) -> None:
    st.markdown(_LAYOUT, unsafe_allow_html=True)
    st.header("Konto")
    st.caption("Din plan styrer, hvilke aktier TraderDash kan analysere.")

    email_col, plan_col, status_col = st.columns(3)
    email_col.metric("E-mail", user.email)
    plan_col.metric("Plan", plans.PLAN_OFFERS[active_plan].name)
    status_col.metric("Abonnement", plans.status_label(user.subscription_status))
    if accounts.developer_override_enabled() and user.plan != active_plan:
        st.caption("Udviklertest. Kontoens plan ændres ikke.")
    if st.button("Log ud", key="account_logout"):
        logout()

    st.subheader("Planer")
    columns = st.columns(len(plans.offers()))
    for column, offer in zip(columns, plans.offers()):
        kind = plans.relation(active_plan, offer)
        with column:
            with st.container(border=True):
                if kind == "current":
                    st.markdown('<span class="td-current"></span>', unsafe_allow_html=True)
                    st.markdown("**Current plan**")
                st.markdown(f"### {offer.name}")
                st.markdown(f"**{plans.price_label(offer)}**")
                if offer.price_note:
                    st.caption(offer.price_note)
                st.write(offer.description)
                for feature in offer.features:
                    st.markdown(f"- {feature}")
                if kind == "upgrade":
                    if st.button(plans.action_label(active_plan, offer), key=f"upgrade_{offer.key}", type="primary", width="stretch"):
                        st.session_state.checkout_notice = plans.request_checkout(offer.key)
                elif kind == "included":
                    st.caption(plans.action_label(active_plan, offer))

    notice = st.session_state.get("checkout_notice")
    if notice:
        st.info(notice)

    if accounts.developer_override_enabled():
        with st.expander("Developer details"):
            st.text(f"user_id: {user.user_id}")
            st.text(f"stripe_customer_id: {user.stripe_customer_id or '—'}")
            st.text(f"stripe_subscription_id: {user.stripe_subscription_id or '—'}")
