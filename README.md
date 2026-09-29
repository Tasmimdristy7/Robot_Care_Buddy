# Robot Care Buddy

A small Python/Django study planner with a floating illustrated robot that reminds you about exams and assignments in speech bubbles.

## Three major functionalities

1. **Task management:** create, edit, and delete exams and assignments with course names and timezone-aware deadlines, persisted in SQLite.
2. **Deadline reminders:** the robot floats into the app when a task is due within its chosen 1-hour, 1-day, or 2-day reminder window, or overdue; snooze for 15 minutes, dismiss for 30 minutes in the current page, or complete from the bubble. Checks run every 30 seconds and when you return to the tab.
3. **Progress tracking:** complete/reopen tasks, search by task or course, filter upcoming/overdue/completed tasks, and see workload and completion counts.

## Run locally

Python 3.10+ is required. This is a local, single-user application with no accounts.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8002
```

Open http://127.0.0.1:8002/. On Windows, activate with `.venv\Scripts\activate`.

Add an assignment with a deadline an hour from now to see a real reminder. “Meet your buddy” shows a sample greeting without creating a task. Snoozes survive reloads; dismissed reminders may return after reload. Tasks remain in the local `db.sqlite3` file, which is excluded from Git.

Dates are entered and displayed in the browser's timezone and sent as explicit UTC timestamps. Overdue tasks appear under Overdue or All. The Upcoming tab excludes completed and overdue tasks.

## Open-source reference

**Simply Todo App** by ptyadana: https://github.com/ptyadana/django-B-simple-todo

License: MIT. Its README describes a small Django app for adding and completing daily tasks.I have  Used its documented functionality and small application scope as a reference, not its source code. No reference code, artwork, templates, or dependencies were copied.

| Reference functionality | Our independent implementation |
| --- | --- |
| Add tasks | Add assignments/exams with course and deadline |
| Complete tasks | Complete/reopen tasks and show progress |
| View daily to-do list | Searchable list with upcoming, overdue, and completed views |

Our deadline checks, snooze behavior, rounded robot artwork, and floating speech-bubble interface are original additions. Both projects remain small task-management applications; this is not a clone of a large planner platform.

## AI tool used

**OpenAI Codex** assisted with planning, original SVG artwork, tests, debugging, and documentation. The reference was reviewed through its README and licensing information. I wrote the implementation independently for this assignment.

## Validation

```sh
python manage.py check
python manage.py test
python manage.py collectstatic --noinput
```

Tests cover CRUD, invalid input, reminder eligibility, snooze expiry, completion exclusion, timezone conversion, CSRF enforcement, and missing routes. Browser JavaScript handles animation and polling; Django handles validation, persistence, and reminder selection.

## Scope

Reminders work inside the open application, not over other desktop apps or while closed. This version is intended for a single user on localhost; it has no access controls and should not be exposed publicly as a shared planner. GitHub hosts the source; a Django server is needed to run the application. No external AI service, email service, or paid API is required.

Future tasks are tracked in GitHub Issues and the assignment Project board.

## Custom reminder timing

Choose **Remind me** when adding or editing a task: 1 hour, 1 day, or 2 days before its deadline. Existing tasks default to 2 days. Overdue tasks remain eligible; completed and snoozed tasks stay excluded. The summary’s 48-hour count remains a workload overview.

## Recurring study tasks

Choose **Daily** or **Weekly** under Repeat. Completing a task creates one next occurrence from its previous deadline and preserves the completed task. The next task inherits the title, course, type, lead time, and recurrence. Daily/weekly deadlines retain their local clock time in the timezone captured when the task was created, including daylight saving changes (nonexistent spring-forward times shift forward by the gap).

Retrying completion or reopening and completing the same historical task never creates another successor. Edit the next open occurrence to change future repeats, or set Repeat to Never to stop. Completing an overdue task advances one interval at a time; missed sessions are not silently skipped.

## Quiet hours

Expand **Buddy quiet hours**, enable it, and save a start, end, and timezone (initially your browser’s timezone). Settings persist in SQLite. For example, 22:00–08:00 pauses deadline bubbles overnight. The start is inclusive and the end is exclusive; equal times are rejected while enabled. Uncheck Enable to turn the feature off.

Quiet hours use the saved timezone, including daylight saving changes. Existing deadline bubbles disappear on the next reminder poll; eligible reminders resume after quiet hours on the next poll (within 30 seconds while the tab is visible). Snoozes and completed tasks still apply. Jokes and manually requested greetings remain available.
