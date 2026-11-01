# 1. Patch backend/app/engine/automation.py to add in-app broadcast and admin emails on JIT expiry
path_automation = r'D:\AccessReaper-v2\backend\app\engine\automation.py'
with open(path_automation, 'r', encoding='utf-8') as f:
    c = f.read()

target_automation = """        db.add(log_entry)
        db.commit()

        if a.identity and a.identity.email and not a.identity.email.endswith("@github.unmatched"):
            send_jit_expiration_email_to_user(
                to_email=a.identity.email,
                user_name=a.identity.name,
                repo_name=repo_name,
                previous_access=old_access,
                new_status_or_access="Revoked",
            )"""

replacement_automation = """        db.add(log_entry)

        # Broadcast in-app notification to all administrators
        try:
            from app.engine.notification_service import broadcast_notification

            broadcast_notification(
                db=db,
                event_type="jit_expired",
                title="JIT Temporary Access Expired",
                message=f"Temporary {old_access} access for {a.identity.name} (@{username or 'user'}) on {repo_name} reached its expiration limit and was automatically revoked.",
                link="#history",
            )
        except Exception as exc:
            logger.warning("Could not broadcast JIT expiration notification: %s", exc)

        db.commit()

        # Notify recipient via email
        if a.identity and a.identity.email and not a.identity.email.endswith("@github.unmatched"):
            try:
                send_jit_expiration_email_to_user(
                    to_email=a.identity.email,
                    user_name=a.identity.name,
                    repo_name=repo_name,
                    previous_access=old_access,
                    new_status_or_access="Revoked",
                )
            except Exception as exc:
                logger.warning("Could not dispatch user JIT expiration email: %s", exc)

        # Also notify administrators via email
        try:
            from app.db.models import User
            admins = db.query(User).filter(User.role == "admin", User.status == "active").all()
            adm_emails = {u.email for u in admins if u.email}
            if not adm_emails and getattr(settings, "SMTP_USER", None):
                adm_emails = {settings.SMTP_USER}
            for adm_email in adm_emails:
                if adm_email != (a.identity.email if a.identity else None):
                    send_jit_expiration_email_to_user(
                        to_email=adm_email,
                        user_name=f"Admin Notice (User: {a.identity.name})",
                        repo_name=repo_name,
                        previous_access=old_access,
                        new_status_or_access="Automatically Revoked",
                    )
        except Exception as exc:
            logger.warning("Could not dispatch admin JIT expiration email: %s", exc)"""

c_norm = c.replace('\r\n', '\n')
target_automation_norm = target_automation.replace('\r\n', '\n')
replacement_automation_norm = replacement_automation.replace('\r\n', '\n')

assert target_automation_norm in c_norm, "Target not found in automation.py"
c_new = c_norm.replace(target_automation_norm, replacement_automation_norm, 1)

with open(path_automation, 'w', encoding='utf-8', newline='\n') as f:
    f.write(c_new)
print("SUCCESS: patched backend/app/engine/automation.py")

# 2. Patch backend/app/api/api_v1/endpoints/automation.py to add POST /automation/reap
path_endpoints = r'D:\AccessReaper-v2\backend\app\api\api_v1\endpoints\automation.py'
with open(path_endpoints, 'r', encoding='utf-8') as f:
    c2 = f.read()

target_endpoints = """@router.post("/automation/trigger")
def trigger_automated_cycle(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    from app.engine.automation import execute_automatic_cycle
    from app.schemas.serializers import serialize_audit_run

    audit_run = execute_automatic_cycle(db, actor=f"Automated audit ({user.name})")
    if not audit_run:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "AUDIT_IN_PROGRESS",
                    "message": "An IAM audit is already in progress. Please wait for it to complete.",
                }
            },
        )
    return serialize_audit_run(audit_run)"""

addition_endpoints = target_endpoints + """


@router.post("/automation/reap")
def trigger_immediate_reap(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    \"\"\"
    Executes an immediate check and revocation of any expired JIT temporary leases.
    \"\"\"
    from app.engine.automation import process_jit_expirations

    count = process_jit_expirations(db)
    return {"reaped_count": count}"""

c2_norm = c2.replace('\r\n', '\n')
target_endpoints_norm = target_endpoints.replace('\r\n', '\n')
addition_endpoints_norm = addition_endpoints.replace('\r\n', '\n')

assert target_endpoints_norm in c2_norm, "Target not found in endpoints/automation.py"
c2_new = c2_norm.replace(target_endpoints_norm, addition_endpoints_norm, 1)

with open(path_endpoints, 'w', encoding='utf-8', newline='\n') as f:
    f.write(c2_new)
print("SUCCESS: patched backend/app/api/api_v1/endpoints/automation.py")

# 3. Patch backend/app/core/scheduler.py to change JIT reaper interval to 10 seconds
path_sched = r'D:\AccessReaper-v2\backend\app\core\scheduler.py'
with open(path_sched, 'r', encoding='utf-8') as f:
    c3 = f.read()

c3_new = c3.replace("trigger=IntervalTrigger(seconds=15)", "trigger=IntervalTrigger(seconds=10)")
with open(path_sched, 'w', encoding='utf-8', newline='\n') as f:
    f.write(c3_new)
print("SUCCESS: patched backend/app/core/scheduler.py")
