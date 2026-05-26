from django.db import connections


def get_group_ids_for_user(user_id) -> list:
    with connections['aura_db'].cursor() as cursor:
        cursor.execute(
            'SELECT customgroup_id FROM auth_user_custom_groups WHERE user_id = %s',
            [user_id],
        )
        return [row[0] for row in cursor.fetchall()]


def get_user_ids_for_group(group_id) -> list:
    with connections['aura_db'].cursor() as cursor:
        cursor.execute(
            'SELECT user_id FROM auth_user_custom_groups WHERE customgroup_id = %s::uuid',
            [str(group_id)],
        )
        return [row[0] for row in cursor.fetchall()]


def get_user_ids_for_groups(group_ids: list) -> list:
    if not group_ids:
        return []
    str_ids = [str(g) for g in group_ids]
    with connections['aura_db'].cursor() as cursor:
        placeholders = ','.join(['%s::uuid'] * len(str_ids))
        cursor.execute(
            f'SELECT DISTINCT user_id FROM auth_user_custom_groups WHERE customgroup_id IN ({placeholders})',
            str_ids,
        )
        return [row[0] for row in cursor.fetchall()]


def count_members_for_group(group_id) -> int:
    with connections['aura_db'].cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) FROM auth_user_custom_groups WHERE customgroup_id = %s',
            [str(group_id)],
        )
        return cursor.fetchone()[0]


def get_member_counts_all_groups() -> dict:
    with connections['aura_db'].cursor() as cursor:
        cursor.execute(
            """
            SELECT customgroup_id::text, COUNT(DISTINCT user_id) AS total_users
            FROM auth_user_custom_groups
            GROUP BY customgroup_id
            """
        )
        return {row[0]: row[1] for row in cursor.fetchall()}


def set_groups_for_user(user_id, group_ids: list) -> None:
    with connections['aura_db'].cursor() as cursor:
        if group_ids:
            placeholders = ','.join(['%s::uuid'] * len(group_ids))
            cursor.execute(
                f'DELETE FROM auth_user_custom_groups '
                f'WHERE user_id = %s AND customgroup_id NOT IN ({placeholders})',
                [user_id] + list(group_ids),
            )
            for gid in group_ids:
                cursor.execute(
                    'INSERT INTO auth_user_custom_groups (user_id, customgroup_id) '
                    'VALUES (%s, %s::uuid) ON CONFLICT DO NOTHING',
                    [user_id, gid],
                )
        else:
            cursor.execute(
                'DELETE FROM auth_user_custom_groups WHERE user_id = %s',
                [user_id],
            )


def set_users_for_group(group_id, user_ids: list) -> None:
    group_id_str = str(group_id)
    with connections['aura_db'].cursor() as cursor:
        if user_ids:
            placeholders = ','.join(['%s'] * len(user_ids))
            cursor.execute(
                f'DELETE FROM auth_user_custom_groups '
                f'WHERE customgroup_id = %s::uuid AND user_id NOT IN ({placeholders})',
                [group_id_str] + list(user_ids),
            )
            for uid in user_ids:
                cursor.execute(
                    'INSERT INTO auth_user_custom_groups (user_id, customgroup_id) '
                    'VALUES (%s, %s::uuid) ON CONFLICT DO NOTHING',
                    [uid, group_id_str],
                )
        else:
            cursor.execute(
                'DELETE FROM auth_user_custom_groups WHERE customgroup_id = %s::uuid',
                [group_id_str],
            )
