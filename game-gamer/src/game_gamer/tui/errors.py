"""Player explanations of stable engine and request codes."""
from .i18n import message_key, t

ERROR_MESSAGES = {
    'actor_mismatch': message_key('errors.actor_mismatch'),
    'agreement_version_conflict': message_key('errors.agreement_version_conflict'),
    'already_accepted': message_key('errors.already_accepted'),
    'already_recalled_connection': message_key('errors.already_recalled_connection'),
    'ambiguous_or_unknown_filter_choose_a_unique_name': message_key('errors.ambiguous_or_unknown_filter_choose_a_unique_name'),
    'gathering_attendance_required': message_key('errors.gathering_attendance_required'),
    'history_time_range_reversed': message_key('errors.history_time_range_reversed'),
    'history_time_requires_timezone': message_key('errors.history_time_requires_timezone'),
    'independent_verifier_required': message_key('errors.independent_verifier_required'),
    'invalid_body': message_key('errors.invalid_body'),
    'invalid_command': message_key('errors.invalid_command'),
    'invalid_transition': message_key('errors.invalid_transition'),
    'invitation_delivery_failed': message_key('errors.invitation_delivery_failed'),
    'missing_authorization': message_key('errors.missing_authorization'),
    'object_not_present_at_this_state': message_key('errors.object_not_present_at_this_state'),
    'request_not_found': message_key('errors.request_not_found'),
    'resource_overcommitment': message_key('errors.resource_overcommitment'),
    'same_origin_required': message_key('errors.same_origin_required'),
    'session_required': message_key('errors.session_required'),
    'stale_version': message_key('errors.stale_version'),
    'unauthorized_approval': message_key('errors.unauthorized_approval'),
    'unauthorized_verifier': message_key('errors.unauthorized_verifier'),
    'unknown_actor': message_key('errors.unknown_actor'),
    'unknown_contract_filter': message_key('errors.unknown_contract_filter'),
    'unknown_scenario': message_key('errors.unknown_scenario'),
    'verified_simulation_binding_required': message_key('errors.verified_simulation_binding_required'),
    'world_scenario_mismatch_choose_another_db': message_key('errors.world_scenario_mismatch_choose_another_db'),
}


def error_message(error):
    code = str(error)
    key = ERROR_MESSAGES.get(code)
    return t('errors.with_code', message=t(key), code=code) if key else code


def error_list(errors):
    return ', '.join(error_message(error) for error in errors)
