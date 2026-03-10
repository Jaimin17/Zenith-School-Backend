from fastapi import APIRouter

from routers import (authentication, user, teacher, student, parent, subject, classes, lesson, exams,
                     assignments, results, events, announcements, admin, attendance, grade, banner,
                     photoGallery, testimonials, achievements, sportsPrograms)
from routers import jobOpenings, jobApplications

from chatbot.router import router

api_router = APIRouter()
# api_router.include_router(user.router, tags=["user"])
api_router.include_router(achievements.router, tags=["achievements"])
api_router.include_router(admin.router, tags=["admin"])
api_router.include_router(announcements.router, tags=["announcements"])
api_router.include_router(assignments.router, tags=["assignments"])
api_router.include_router(attendance.router, tags=["attendance"])
api_router.include_router(authentication.router, tags=["authentication"])
api_router.include_router(banner.router, tags=["banner"])
api_router.include_router(classes.router, tags=["classes"])
api_router.include_router(events.router, tags=["events"])
api_router.include_router(exams.router, tags=["exams"])
api_router.include_router(grade.router, tags=["grade"])
api_router.include_router(jobOpenings.router, tags=["jobOpenings"])
api_router.include_router(jobApplications.router, tags=["jobApplications"])
api_router.include_router(lesson.router, tags=["lesson"])
api_router.include_router(parent.router, tags=["parent"])
api_router.include_router(photoGallery.router, tags=["photoGallery"])
api_router.include_router(results.router, tags=["results"])
api_router.include_router(sportsPrograms.router, tags=["sportsPrograms"])
api_router.include_router(student.router, tags=["student"])
api_router.include_router(subject.router, tags=["subject"])
api_router.include_router(teacher.router, tags=["teacher"])
api_router.include_router(testimonials.router, tags=["testimonials"])
api_router.include_router(router, tags=["chatbot"])
