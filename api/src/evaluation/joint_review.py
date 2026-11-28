"""Hash-bound test-only joint-review exception; never an independent P4 sheet."""

from pathlib import Path

PROTOCOL = 'c31-c33-v2-joint-review-test'
ROLES = frozenset({'protocol', 'parent_protocol', 'confirmation', 'acceptance',
                   'primary_source', 'confirmed_primary', 'canonical_primary'})


def exception_files(approval_path, approved):
    """Resolve only pinned files within the release, including freeze provenance."""
    from .recommendation import sha

    references = approved.get('joint_review_files')
    if not isinstance(references, dict) or set(references) != ROLES:
        raise ValueError('Joint review requires all provenance files')
    root = Path(approval_path).resolve().parent
    files = {}
    for role, reference in references.items():
        if not isinstance(reference, dict) or not isinstance(reference.get('path'), str):
            raise ValueError('Invalid joint review file reference')
        relative = Path(reference['path'])
        path = (root / relative).resolve()
        if relative.is_absolute() or '..' in relative.parts or not path.is_relative_to(root):
            raise ValueError('Joint review file must stay within release')
        if sha(path) != reference.get('sha256'):
            raise ValueError('Joint review provenance hash mismatch')
        files[role] = path
    return files


def validate_exception(directory, approval_path, approved, run, expected, sample, primary, cross, final):
    """Check the exception's exact run, test pairs, raw labels and acceptance."""
    from .recommendation import _identity, _sheet, read_json, sha
    from .review import _rows, _indexed, _validate_edit

    files = exception_files(approval_path, approved)
    protocol, parent, confirmation, acceptance = (
        read_json(files[role]) for role in ('protocol', 'parent_protocol', 'confirmation', 'acceptance'))
    if not all(isinstance(record, dict) for record in (protocol, parent, confirmation, acceptance)):
        raise ValueError('Joint review provenance must contain objects')
    binding = dict(snapshot_id=run['snapshot_id'], scenario_sha256=run['scenario_sha256'],
                   run_sha256=sha(directory/'run.json'), pool_sha256=sha(directory/'pool.jsonl'))
    for record in (protocol, confirmation, acceptance):
        if any(record.get(k) != value for k, value in binding.items()):
            raise ValueError('Joint review belongs to another snapshot/scenario/pool/run')
    if (protocol.get('protocol') != PROTOCOL or parent.get('protocol') != 'c31-c33-v1'
            or protocol.get('parent_protocol_sha256') != sha(files['parent_protocol'])
            or protocol.get('exception_scope') != 'test_only_fixed_sample'
            or protocol.get('independent_test_review_satisfied') is not False
            or protocol.get('spec_acceptance_claim') is not False):
        raise ValueError('Joint review protocol must disclose the test-only exception')
    if (confirmation.get('record_type') != 'explicit_user_review_confirmation_and_P4_agreement_attestation'
            or acceptance.get('record_type') != 'user_attested_team_acceptance_of_joint_review_exception'
            or confirmation.get('confirmed_by') != approved['primary_annotator_id']
            or acceptance.get('reported_by') != confirmation['confirmed_by']
            or acceptance.get('review_confirmation_sha256') != sha(files['confirmation'])
            or acceptance.get('shared_review_accepted_by_team_as_reported') is not True
            or acceptance.get('independent_review_performed') is not False
            or confirmation.get('p4_independent_review_verified') is not False
            or confirmation.get('p4_reviewer_identity') is not None
            or confirmation.get('p4_asserted_role') != 'P4'
            or not confirmation.get('user_answer', '').strip()
            or not acceptance.get('user_statement', '').strip()):
        raise ValueError('Joint review acceptance/confirmation missing or misrepresented')
    _identity(confirmation, 'confirmed_by', 'confirmation_recorded_at')
    _identity(acceptance, 'reported_by', 'recorded_at')
    for role, field in [('primary_source', 'source_primary_sha256'),
                        ('confirmed_primary', 'confirmed_primary_sha256'),
                        ('canonical_primary', 'canonical_primary_sha256')]:
        if sha(files[role]) != confirmation.get(field):
            raise ValueError('Joint review primary source hash differs from confirmation')
    if confirmation.get('review_sample_sha256') != sha(directory/'review_sample.json'):
        raise ValueError('Joint review sample changed')
    pairs = confirmation.get('pairs')
    if not isinstance(pairs, list):
        raise ValueError('Joint review needs an explicit pair ledger')
    decisions = {}
    for row in pairs:
        if not isinstance(row, dict) or not isinstance(row.get('scenario_id'), str) or not isinstance(row.get('work_id'), str):
            raise ValueError('Invalid joint review pair identifier')
        pair = (row['scenario_id'], row['work_id'])
        if (pair in decisions or type(row.get('relevance')) is not int
                or row['relevance'] not in (0, 1, 2)
                or type(row.get('p4_agreement_attested')) is not bool):
            raise ValueError('Duplicate/invalid joint review decision')
        decisions[pair] = row
    agreed = {pair for pair, row in decisions.items() if row['p4_agreement_attested']}
    if (set(decisions) != expected or agreed != expected & sample
            or confirmation.get('primary_rows_user_confirmed') != len(expected)
            or confirmation.get('p4_pairs_user_attests_agreement') != len(agreed)):
        raise ValueError('Joint review must cover exactly the test pool and fixed sample')
    if expected & cross.keys():
        raise ValueError('Joint test review must not impersonate an independent P4 sheet')
    raw_cols, raw_rows = _rows(files['primary_source'])
    cols, confirmed_rows = _rows(files['confirmed_primary'])
    raw, confirmed = _indexed(raw_rows), _indexed(confirmed_rows)
    canonical = _sheet(files['canonical_primary'])
    if set(raw_cols) != set(cols) or any(set(sheet) != expected for sheet in (raw, confirmed, canonical)):
        raise ValueError('Joint primary sheets do not match the test pool')
    changed = {'annotator_id', 'annotated_at', 'review_status', 'reviewer_confirmed', 'review_note'}
    for pair, decision in decisions.items():
        if not _validate_edit(confirmed[pair], 'primary'):
            raise ValueError('Joint primary reviewer has not confirmed')
        if any(raw[pair][c] != confirmed[pair][c] for c in raw_cols if c not in changed):
            raise ValueError('Joint primary changed source metadata/labels/evidence')
        for row in (primary[pair], canonical[pair], confirmed[pair], final[pair]):
            if (row.get('relevance') != str(decision['relevance'])
                    or row.get('rationale') != raw[pair]['rationale']
                    or row.get('evidence') != raw[pair]['evidence']):
                raise ValueError('Joint final must preserve confirmed source labels and evidence')
        for row in (canonical[pair], confirmed[pair]):
            if (row.get('annotator_id') != approved['primary_annotator_id']
                    or row.get('reviewer_confirmed') != 'yes' or row.get('review_status') != 'confirmed'
                    or any(row.get(k) != value for k, value in binding.items())):
                raise ValueError('Joint primary identity/confirmation/binding differs')
            _identity(row, 'annotator_id', 'annotated_at')
        row = final[pair]
        if (row.get('review_mode') != 'joint_review_exception'
                or row.get('joint_review_confirmation_sha256') != sha(files['confirmation'])
                or row.get('team_exception_sha256') != sha(files['acceptance'])
                or row.get('original_independent_protocol_satisfied') != 'no'
                or row.get('approved_by') != approved['approved_by']):
            raise ValueError('Joint final must disclose and bind its exception')
