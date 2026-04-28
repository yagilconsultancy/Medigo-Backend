from fastapi import APIRouter

from app.schemas.booking_flow import (
    BookingAppointmentOption,
    BookingAudienceOption,
    BookingRecurringFrequencyOption,
    BookingServiceOption,
    BookingTripStructureOption,
    BookingVehicleOption,
    PublicBookingConfigResponse,
)
from mediride_common.schemas.enums import RecurringFrequency, TripStructure, TripType
from mediride_common.schemas.responses import StandardResponse

router = APIRouter(prefix="/public/booking-flow")


@router.get("/config", response_model=StandardResponse[PublicBookingConfigResponse])
async def get_public_booking_flow_config():
    """Public booking wizard metadata for website/mobile flows."""
    return StandardResponse(
        data=PublicBookingConfigResponse(
            audiences=[
                BookingAudienceOption(
                    code="individual",
                    role="rider",
                    label="Individual",
                    description="Book for yourself or a family member.",
                    features=[
                        "Personal transport",
                        "Family bookings",
                        "Ride tracking",
                    ],
                ),
                BookingAudienceOption(
                    code="facility",
                    role="facility",
                    label="Facility",
                    description="Book on behalf of patients from a healthcare facility.",
                    features=[
                        "Multi-patient management",
                        "Bulk scheduling",
                        "Staff dashboard",
                    ],
                ),
            ],
            services=[
                BookingServiceOption(
                    trip_type=TripType.TRANSPORT_ONLY,
                    label="Transport Only",
                    description=(
                        "Safe, reliable transport for patients who are independently "
                        "mobile or accompanied."
                    ),
                    features=[
                        "Trained MediGo driver",
                        "Door-to-door service",
                        "Real-time ride tracking",
                        "Up to 2 passengers",
                    ],
                ),
                BookingServiceOption(
                    trip_type=TripType.TRANSPORT_CARE_ASSISTANT,
                    label="Transport + Care Assistant",
                    description=(
                        "Transport with a qualified care assistant for patients who "
                        "need hands-on support."
                    ),
                    features=[
                        "Driver plus care assistant",
                        "Door-to-door support",
                        "Medication and mobility assistance",
                        "Scheduled trips only",
                    ],
                    recommended=True,
                    requires_scheduled=True,
                ),
            ],
            appointments=[
                BookingAppointmentOption(
                    visit_type="dialysis",
                    label="Dialysis",
                    description="Recurring or one-time dialysis transport.",
                    is_dialysis_trip=True,
                ),
                BookingAppointmentOption(
                    visit_type="x_ray_scan",
                    label="X-Ray / Scan",
                    description="Diagnostic imaging appointments.",
                ),
                BookingAppointmentOption(
                    visit_type="medical_checkup",
                    label="Medical Checkup",
                    description="Routine doctor or specialist visit.",
                ),
                BookingAppointmentOption(
                    visit_type="chemotherapy",
                    label="Chemotherapy",
                    description="Cancer treatment and infusion visits.",
                ),
                BookingAppointmentOption(
                    visit_type="physiotherapy",
                    label="Physiotherapy",
                    description="Physical therapy and rehabilitation sessions.",
                ),
                BookingAppointmentOption(
                    visit_type="surgery",
                    label="Surgery",
                    description="Outpatient procedure or surgery visit.",
                ),
                BookingAppointmentOption(
                    visit_type="consultation",
                    label="Consultation",
                    description="Medical consultation or follow-up appointment.",
                ),
                BookingAppointmentOption(
                    visit_type="mental_health",
                    label="Mental Health",
                    description="Mental health and counselling appointments.",
                ),
                BookingAppointmentOption(
                    visit_type="rehabilitation",
                    label="Rehabilitation",
                    description="Structured rehab program or recovery care.",
                ),
                BookingAppointmentOption(
                    visit_type="hospital_discharge",
                    label="Hospital Discharge",
                    description="Pickup from hospital after discharge.",
                ),
                BookingAppointmentOption(
                    visit_type="blood_test_lab",
                    label="Blood Test / Lab",
                    description="Lab work and blood draw visits.",
                ),
                BookingAppointmentOption(
                    visit_type="other",
                    label="Other",
                    description="Any other medical or care-related visit.",
                ),
            ],
            vehicles=[
                BookingVehicleOption(
                    ride_type="ambulatory",
                    label="Medigo Standard",
                    description=(
                        "A modern, comfortable car for ambulatory patients who can "
                        "transfer independently."
                    ),
                    features=[
                        "Up to 3 passengers",
                        "Sedan / SUV",
                        "Door-to-door",
                        "GPS tracked",
                    ],
                ),
                BookingVehicleOption(
                    ride_type="stretcher",
                    label="Medigo Stretcher",
                    description=(
                        "Non-emergency ambulance transport for patients requiring a "
                        "full-length stretcher and clinical crew."
                    ),
                    features=[
                        "1 patient + 2 crew",
                        "Full stretcher",
                        "Medical crew",
                        "Climate controlled",
                    ],
                ),
                BookingVehicleOption(
                    ride_type="wheelchair",
                    label="Medigo Wheelchair",
                    description=(
                        "Accessible van transport with hydraulic lift and wheelchair "
                        "restraints."
                    ),
                    features=[
                        "1 wheelchair + 2 passengers",
                        "Hydraulic lift",
                        "Restraint system",
                        "Wide entry",
                    ],
                ),
            ],
            trip_structures=[
                BookingTripStructureOption(
                    trip_structure=TripStructure.ONE_WAY,
                    label="One Way",
                    description="Single journey.",
                ),
                BookingTripStructureOption(
                    trip_structure=TripStructure.ROUND_TRIP,
                    label="Round Trip",
                    description="Return journey included.",
                ),
            ],
            recurring_frequencies=[
                BookingRecurringFrequencyOption(
                    frequency=RecurringFrequency.DAILY,
                    label="Daily",
                    description="Repeat every day.",
                ),
                BookingRecurringFrequencyOption(
                    frequency=RecurringFrequency.WEEKLY,
                    label="Weekly",
                    description="Repeat every week.",
                ),
                BookingRecurringFrequencyOption(
                    frequency=RecurringFrequency.BIWEEKLY,
                    label="Bi-Weekly",
                    description="Repeat every two weeks.",
                ),
                BookingRecurringFrequencyOption(
                    frequency=RecurringFrequency.MONTHLY,
                    label="Monthly",
                    description="Repeat every month.",
                ),
            ],
        )
    )
