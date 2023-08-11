
from typing import Optional, List
from datetime import datetime
from fastapi import (
    HTTPException,
    APIRouter,
    Response,
    Form
)

from app.common.database.repositories import (
    beatmaps,
    comments,
    users
)

from app.common.constants import CommentTarget, Permissions
from app.common.database import DBComment
from app.common.cache import status

router = APIRouter()

import bcrypt
import app

@router.post('/osu-comment.php')
async def get_comments(
    username: str = Form(..., alias='u'),
    password: str = Form(..., alias='p'),
    playmode: int = Form(..., alias='m'),
    replay_id: int = Form(..., alias='r'),
    beatmap_id: int = Form(..., alias='b'),
    set_id: int = Form(..., alias='s'),
    action: str = Form(..., alias='a'),
    content: Optional[str] = Form(None, alias='comment'),
    time: Optional[int] = Form(None, alias='starttime'),
    color: Optional[str] = Form(None, alias='f'),
    target: Optional[str] = Form(None),
):
    if not (user := users.fetch_by_name(username)):
        raise HTTPException(401, detail="Auth")

    if not bcrypt.checkpw(password.encode(), user.bcrypt.encode()):
        raise HTTPException(401, detail="Auth")

    if not status.exists(user.id):
        raise HTTPException(401, detail='Bancho')

    users.update(user.id, {'latest_activity': datetime.now()})

    if action == 'get':
        db_comments: List[DBComment] = []
        db_comments.extend(comments.fetch_many(replay_id, 'replay'))
        db_comments.extend(comments.fetch_many(beatmap_id, 'map'))
        db_comments.extend(comments.fetch_many(set_id, 'song'))

        response: List[str] = []

        for comment in db_comments:
            comment_format = comment.format if comment.format != None else ""
            comment_format = f'{comment_format}{f"|{comment.color}" if comment.color else ""}'

            response.append(
                '\t'.join([
                    str(comment.time),
                    comment.target_type,
                    comment_format,
                    comment.comment
                ])
            )

        return Response('\n'.join(response))

    elif action == 'post':
        try:
            target = CommentTarget(target)
        except ValueError:
            raise HTTPException(400, detail="Invalid target")

        if not (content):
            raise HTTPException(400, detail="No content")

        if len(content) > 80:
            raise HTTPException(400, detail="Content size")

        if not (beatmap := beatmaps.fetch_by_id(beatmap_id)):
            raise HTTPException(404, detail="Beatmap not found")

        target_id = {
            CommentTarget.Replay: replay_id,
            CommentTarget.Map: beatmap_id,
            CommentTarget.Song: set_id
        }[target]

        permissions = Permissions(user.permissions)

        if Permissions.Supporter not in permissions:
            color = None

        comment_format = 'player'

        if beatmap.beatmapset.creator == user.name:
            comment_format = 'creator'
        elif Permissions.BAT in permissions:
            comment_format = 'bat'
        elif Permissions.Supporter in permissions:
            comment_format = 'subscriber'

        comments.create(
            target_id,
            target.name.lower(),
            user.id,
            time,
            content,
            comment_format,
            beatmap.mode,
            color
        )

        app.session.logger.info(
            f'<{user.name} ({user.id})> -> Submitted comment on {target.name}: "{content}".'
        )

        return Response('ok')

    raise HTTPException(400, detail="Invalid action")
