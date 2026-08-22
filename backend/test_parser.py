from backend.app.ai.parser import extract_information
from backend.app.schemas.management import ManagementData


message = (
    "I have a meeting tomorrow from 3 PM to 4 PM. "
    "I am free from 5 PM to 9 PM. "
    "I need two hours to complete my ML assignment. "
    "Remind me about the meeting 30 minutes before."
)

data = extract_information(message)

validated_data = ManagementData.model_validate(data)

print("\nVALIDATED MANAGEMENT DATA\n")
print(validated_data.model_dump_json(indent=2))