from backend.app.database.connection import SessionLocal
from backend.app.ai.parser import extract_information
from backend.app.schemas.management import ManagementData
from backend.app.services.management_service import save_management_data


message = (
    "I have a meeting tomorrow from 3 PM to 4 PM. "
    "I am free from 5 PM to 9 PM. "
    "I need two hours to complete my ML assignment. "
    "Remind me about the meeting 30 minutes before."
)




raw_data = extract_information(message)




management_data = ManagementData.model_validate(
    raw_data
)




db = SessionLocal()

try:

    result = save_management_data(
        db,
        management_data
    )

    print("\nDATA SAVED SUCCESSFULLY\n")

    print(result)

finally:

    db.close()