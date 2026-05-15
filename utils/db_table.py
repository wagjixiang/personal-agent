'''
Author: Wang Jixiang
Date: 2026-05-12 18:00:52
LastEditors: Wang Jixiang
LastEditTime: 2026-05-15 15:43:17
Description: table description
'''
DATABASE_SCHEMA = {
    "tb_college": {
        "description": "学院信息表，查询学院的介绍以及学院排名非常有用",

        "fields": {
            "col_id": "学院ID",
            "col_name": "学院名称",
            "col_intro": "学院简介",
            "col_order": "学院排名（综合学院排名：包含学生满意度，学科评估结果等）"
        }
    },

    "tb_student": {
        "description": "学生信息表，查询学生的基本信息非常有用",

        "fields": {
            "stu_id": "学生ID",
            "stu_name": "学生姓名",
            "stu_sex": "学生性别",
            "stu_birth": "学生出生日期",
            "stu_addr": "学生籍贯（出生地址）",
            "col_id": "所属学院ID（外键）"
        }
    },

    "tb_teacher": {
        "description": "教师信息表，查询教师的姓名和职称非常有用",

        "fields": {
            "tea_id": "教师ID",
            "tea_name": "教师姓名",
            "tea_title": "教师职称",
            "col_id": "所属学院ID（外键）"
        }
    },

    "tb_course": {
        "description": "课程信息表，查询课程名称和学分非常有用",

        "fields": {
            "cou_id": "课程ID",
            "cou_name": "课程名称",
            "cou_credit": "课程学分",
            "tea_id": "任课教师ID（外键）"
        }
    },

    "tb_record": {
        "description": "选课记录表，查询学生的选课记录以及成绩非常有用",

        "fields": {
            "rec_id": "记录ID",
            "stu_id": "学生ID（外键）",
            "cou_id": "课程ID（外键）",
            "sel_date": "选课日期",
            "score": "成绩"
        }
    }
}