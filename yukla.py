"""
Foydalanuvchilarni txt fayldan bazaga yuklash skripti
Oxangxbot_users.txt dan user_id larni o'qib, users jadvaliga qo'shadi
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.database.connection import engine, async_session, init_db
from app.database.models import User, get_uzb_time


async def load_users_from_file(file_path: str = "Oxangxbot_users.txt"):
    """
    Fayldan user_id larni o'qib bazaga yuklash
    Bulk insert bilan tez va optimal ishlaydi
    """
    # Faylni o'qish
    file = Path(file_path)
    if not file.exists():
        print(f"❌ Fayl topilmadi: {file_path}")
        return
    
    # User ID larni o'qish
    user_ids = []
    with open(file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and line.isdigit():
                user_ids.append(int(line))
    
    if not user_ids:
        print("❌ Faylda user ID topilmadi")
        return
    
    print(f"📄 Fayldan {len(user_ids)} ta user ID o'qildi")
    
    # Bazani tayyorlash
    await init_db()
    
    async with async_session() as session:
        # Mavjud user_id larni olish
        result = await session.execute(
            select(User.user_id)
        )
        existing_ids = {row[0] for row in result.fetchall()}
        
        # Yangi user_id larni filterlash
        new_user_ids = [uid for uid in user_ids if uid not in existing_ids]
        
        print(f"✅ Mavjud userlar: {len(existing_ids)}")
        print(f"🆕 Yangi userlar: {len(new_user_ids)}")
        
        if not new_user_ids:
            print("ℹ️ Barcha userlar allaqachon bazada")
            return
        
        # Bulk insert - 1000 tadan batch qilib qo'shish
        batch_size = 1000
        total_added = 0
        current_time = get_uzb_time()
        
        for i in range(0, len(new_user_ids), batch_size):
            batch = new_user_ids[i:i + batch_size]
            
            # User obyektlarini yaratish
            users_to_add = [
                User(
                    user_id=uid,
                    username=None,
                    language_code="uz",
                    created_at=current_time,
                    updated_at=current_time
                )
                for uid in batch
            ]
            
            session.add_all(users_to_add)
            await session.commit()
            
            total_added += len(batch)
            progress = (total_added / len(new_user_ids)) * 100
            print(f"⏳ Qo'shildi: {total_added}/{len(new_user_ids)} ({progress:.1f}%)")
        
        print(f"\n🎉 Muvaffaqiyatli yakunlandi!")
        print(f"📊 Jami qo'shilgan: {total_added} ta yangi user")
        print(f"📊 Bazadagi jami userlar: {len(existing_ids) + total_added}")


async def main():
    """Asosiy funksiya"""
    print("=" * 50)
    print("🚀 Userlarni bazaga yuklash boshlandi")
    print("=" * 50)
    
    # Default fayl yoki argument orqali
    file_path = sys.argv[1] if len(sys.argv) > 1 else "Oxangxbot_users.txt"
    
    await load_users_from_file(file_path)
    
    # Engine ni yopish
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
