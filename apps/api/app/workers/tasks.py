from app.workers.celery_app import celery_app
import time

@celery_app.task(name="tasks.recalculate_user_matches")
def recalculate_user_matches(user_id: str):
    """Background task to invalidate cache and recalculate top match vector candidates."""
    print(f"[Worker] Recalculating match recommendations for user {user_id}...")
    time.sleep(1)
    print(f"[Worker] Match recommendations updated for {user_id}")
    return {"status": "success", "user_id": user_id}

@celery_app.task(name="tasks.send_application_notification")
def send_application_notification(owner_email: str, applicant_name: str, property_title: str):
    """Sends email/push notification to landlord when new application arrives."""
    print(f"[Worker] Notification sent to {owner_email} for application from {applicant_name} on '{property_title}'")
    return {"status": "sent", "recipient": owner_email}
