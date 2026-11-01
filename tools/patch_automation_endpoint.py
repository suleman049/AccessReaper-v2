path = r'D:\AccessReaper-v2\backend\app\api\api_v1\endpoints\automation.py'
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

target = """@router.post("/automation/autopilot/enforce")
def trigger_autopilot_enforce(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    from app.engine.automation import enforce_autopilot

    return enforce_autopilot(db, actor=f"{user.name} (Auto-Pilot Trigger)")"""

addition = """@router.post("/automation/autopilot/enforce")
def trigger_autopilot_enforce(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    from app.engine.automation import enforce_autopilot

    return enforce_autopilot(db, actor=f"{user.name} (Auto-Pilot Trigger)")


@router.post("/automation/trigger")
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

c_norm = c.replace('\r\n', '\n')
target_norm = target.replace('\r\n', '\n')
addition_norm = addition.replace('\r\n', '\n')

if target_norm in c_norm:
    c_new = c_norm.replace(target_norm, addition_norm, 1)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(c_new)
    print("SUCCESS: patched automation.py")
else:
    print("WARNING: target not found")
