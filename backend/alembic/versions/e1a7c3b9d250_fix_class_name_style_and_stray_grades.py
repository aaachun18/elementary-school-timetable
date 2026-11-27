"""fix class name styles and grades outside the school's type (data only)

- classes.name_style: d71a3c5e8b20 added the column with a server default
  of 'NUMBER', so every class that already existed (一年甲班 ...) was
  labelled 一二三 although its name says 甲乙丙. Each class now gets the
  style its own name is written in; a name that matches no style keeps
  'NUMBER'.
- grades: a school only has the grades of its type (國小 1-6, 國中 7-9,
  高中 10-12). A grade outside that range with no class in it is deleted,
  with its 科目需求 and semester open slots; one that still has classes is
  kept (nothing is lost) and only stops being offered when it is emptied.

Revision ID: e1a7c3b9d250
Revises: d71a3c5e8b20
Create Date: 2026-10-21 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1a7c3b9d250'
down_revision: Union[str, Sequence[str], None] = 'd71a3c5e8b20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The tokens between 「X年」 and 「班」 (app/services/school_structure.py).
HEAVENLY_STEMS = ('甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸')
VIRTUES = ('忠', '孝', '仁', '愛', '信', '義', '和', '平')

LEVELS_BY_TYPE = {
    'ELEMENTARY': (1, 6),
    'JUNIOR_HIGH': (7, 9),
    'SENIOR_HIGH': (10, 12),
}


def _class_token(name: str) -> str | None:
    """「一年甲班」 -> 「甲」; None for a name not shaped like that."""
    if '年' not in name or not name.endswith('班'):
        return None
    return name.split('年', 1)[1][:-1]


def _fix_name_styles(connection: sa.engine.Connection) -> None:
    for class_id, name in connection.execute(sa.text('SELECT id, name FROM classes')).all():
        token = _class_token(name)
        if token in HEAVENLY_STEMS:
            style = 'HEAVENLY_STEM'
        elif token in VIRTUES:
            style = 'VIRTUE'
        else:
            continue
        connection.execute(
            sa.text('UPDATE classes SET name_style = :style WHERE id = :id'),
            {'style': style, 'id': class_id},
        )


def _delete_stray_grades(connection: sa.engine.Connection) -> None:
    for school_type, (first, last) in LEVELS_BY_TYPE.items():
        stray = (
            'SELECT g.id FROM grades g JOIN schools s ON s.id = g.school_id '
            'WHERE s.school_type = :type AND (g.level < :first OR g.level > :last) '
            'AND NOT EXISTS (SELECT 1 FROM classes c WHERE c.grade_id = g.id)'
        )
        params = {'type': school_type, 'first': first, 'last': last}
        for table in ('grade_subject_requirements', 'semester_grade_time_slots'):
            connection.execute(
                sa.text(f'DELETE FROM {table} WHERE grade_id IN ({stray})'), params
            )
        connection.execute(sa.text(f'DELETE FROM grades WHERE id IN ({stray})'), params)


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()
    _fix_name_styles(connection)
    _delete_stray_grades(connection)


def downgrade() -> None:
    """Downgrade schema.

    Nothing to undo: only wrong data was corrected, and the schema is
    unchanged."""
