"""
iOS Specializations endpoint - يرجع الاختصاصات بنفس IDs الموجودة في Swift
بدون التأثير على Android API الحالي
"""
from fastapi import APIRouter
from typing import List, Dict

router = APIRouter()

# الاختصاصات بنفس الترتيب والـ IDs الموجودة في Swift (iOS)
IOS_SPECIALIZATIONS = [
    {"id": 1, "name": "طبيب عام", "key": "general"},
    {"id": 2, "name": "الجهاز الهضمي", "key": "gastroenterologist"},
    {"id": 3, "name": "الصدرية والقلبية", "key": "cardiologist"},
    {"id": 4, "name": "أمراض جلدية", "key": "dermatologist"},
    {"id": 5, "name": "مخ وأعصاب", "key": "neurologist"},
    {"id": 6, "name": "طب نفسي", "key": "psychiatrist"},
    {"id": 7, "name": "طب أطفال", "key": "pediatrician"},
    {"id": 8, "name": "نسائية و توليد / رعاية حوامل", "key": "obstetrician"},
    {"id": 9, "name": "جراحة العظام و المفاصل و الكسور", "key": "orthopedic"},
    {"id": 10, "name": "جراحة العيون", "key": "ophthalmologist"},
    {"id": 11, "name": "أنف وأذن و حنجرة", "key": "otolaryngologist"},
    {"id": 12, "name": "الغدد الصماء", "key": "endocrinologist"},
    {"id": 13, "name": "صدرية و تنفسية", "key": "pulmonologist"},
    {"id": 14, "name": "أمراض الكلى", "key": "nephrologist"},
    {"id": 15, "name": "طب الأسنان", "key": "dentistry"},
    {"id": 16, "name": "جراحة تجميلة", "key": "plastic"},
    {"id": 17, "name": "المسالك البولية", "key": "urologist"},
    {"id": 18, "name": "أخصائي المناعة", "key": "immunologist"},
    {"id": 19, "name": "أخصائي أمراض الدم", "key": "hematologist"},
    {"id": 20, "name": "سرطان و اورام", "key": "oncologist"},
]


@router.get("/ios/specializations", response_model=List[Dict])
def get_ios_specializations():
    """
    إرجاع قائمة الاختصاصات بنفس IDs الموجودة في تطبيق iOS (Swift)
    
    هذا الـ endpoint مخصص لتطبيق iOS فقط.
    تطبيق Android يستمر باستخدام الـ endpoint الحالي.
    
    Returns:
        قائمة الاختصاصات مع id و name و key
    """
    return IOS_SPECIALIZATIONS


@router.get("/ios/specializations/{spec_id}", response_model=Dict)
def get_ios_specialization_by_id(spec_id: int):
    """
    إرجاع تخصص واحد حسب الـ ID (iOS)
    
    Args:
        spec_id: رقم التخصص (1-20)
    
    Returns:
        بيانات التخصص أو 404 إذا لم يوجد
    """
    from fastapi import HTTPException
    
    for spec in IOS_SPECIALIZATIONS:
        if spec["id"] == spec_id:
            return spec
    
    raise HTTPException(status_code=404, detail=f"التخصص رقم {spec_id} غير موجود")


def get_specialization_name_by_id(spec_id: int) -> str:
    """
    دالة مساعدة: إرجاع اسم التخصص حسب ID (iOS)
    
    Args:
        spec_id: رقم التخصص
    
    Returns:
        اسم التخصص أو None
    """
    for spec in IOS_SPECIALIZATIONS:
        if spec["id"] == spec_id:
            return spec["name"]
    return None


def get_specialization_id_by_name(name: str) -> int:
    """
    دالة مساعدة: إرجاع ID التخصص حسب الاسم (iOS)
    
    Args:
        name: اسم التخصص
    
    Returns:
        ID التخصص أو None
    """
    # تطبيع النص للمقارنة
    normalized_name = name.strip()
    
    for spec in IOS_SPECIALIZATIONS:
        if spec["name"] == normalized_name:
            return spec["id"]
    
    return None
