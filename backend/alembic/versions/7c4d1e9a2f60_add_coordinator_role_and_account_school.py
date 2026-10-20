"""add COORDINATOR role, users.school_id and teachers.user_id

Task 98: three roles -- ADMIN (系統管理員, no school), COORDINATOR (教學組長)
and TEACHER (一般老師), both of the latter bound to one school. A TEACHER
account and its Teacher are one to one (teachers.user_id, unique).

Existing TEACHER accounts have no school yet; they are bound to the first
school (by id), or to a newly created "預設學校" if there is none, so the
new CHECK can hold. Existing ADMIN accounts stay ADMIN (no school).

Revision ID: 7c4d1e9a2f60
Revises: 5b7e2c91d4a8
Create Date: 2026-10-19 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c4d1e9a2f60'
down_revision: Union[str, Sequence[str], None] = '5b7e2c91d4a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLE_CHECK_NAME = 'ck_users_role_valid'
SCHOOL_CHECK_NAME = 'ck_users_school_matches_role'
USERS_SCHOOL_FK_NAME = 'fk_users_school_id_schools'
TEACHERS_USER_FK_NAME = 'fk_teachers_user_id_users'
TEACHERS_USER_UNIQUE_NAME = 'uq_teachers_user_id'
DEFAULT_SCHOOL_NAME = '預設學校'


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(ROLE_CHECK_NAME, 'users', type_='check')
    op.create_check_constraint(
        ROLE_CHECK_NAME, 'users', "role IN ('ADMIN', 'COORDINATOR', 'TEACHER')"
    )

    op.add_column('users', sa.Column('school_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        USERS_SCHOOL_FK_NAME, 'users', 'schools', ['school_id'], ['id']
    )

    connection = op.get_bind()
    has_teacher_accounts = connection.scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM users WHERE role = 'TEACHER')")
    )
    if has_teacher_accounts:
        school_id = connection.scalar(sa.text("SELECT min(id) FROM schools"))
        if school_id is None:
            school_id = connection.scalar(
                sa.text(
                    "INSERT INTO schools (name, is_active) VALUES (:name, true) "
                    "RETURNING id"
                ),
                {'name': DEFAULT_SCHOOL_NAME},
            )
        connection.execute(
            sa.text("UPDATE users SET school_id = :school_id WHERE role = 'TEACHER'"),
            {'school_id': school_id},
        )

    op.create_check_constraint(
        SCHOOL_CHECK_NAME, 'users', "(role = 'ADMIN') = (school_id IS NULL)"
    )

    op.add_column('teachers', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        TEACHERS_USER_FK_NAME, 'teachers', 'users', ['user_id'], ['id']
    )
    op.create_unique_constraint(TEACHERS_USER_UNIQUE_NAME, 'teachers', ['user_id'])


def downgrade() -> None:
    """Downgrade schema. COORDINATOR accounts become ADMIN again (the
    closest of the two old roles: they managed scheduling data)."""
    op.drop_constraint(TEACHERS_USER_UNIQUE_NAME, 'teachers', type_='unique')
    op.drop_constraint(TEACHERS_USER_FK_NAME, 'teachers', type_='foreignkey')
    op.drop_column('teachers', 'user_id')

    op.drop_constraint(SCHOOL_CHECK_NAME, 'users', type_='check')
    op.drop_constraint(USERS_SCHOOL_FK_NAME, 'users', type_='foreignkey')
    op.drop_column('users', 'school_id')

    op.drop_constraint(ROLE_CHECK_NAME, 'users', type_='check')
    op.execute("UPDATE users SET role = 'ADMIN' WHERE role = 'COORDINATOR'")
    op.create_check_constraint(
        ROLE_CHECK_NAME, 'users', "role IN ('ADMIN', 'TEACHER')"
    )
