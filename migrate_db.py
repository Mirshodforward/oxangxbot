import asyncio
from sqlalchemy import text
from app.database.connection import engine, Base
from app.database import models

async def migrate_database():
    print("Migratsiya boshlanmoqda...")
    
    async with engine.begin() as conn:
        # 1. Yangi jadvallarni yaratish (CacheStats, YouTubeCache, MusicSearchCache agar yo'q bo'lsa)
        print("Yangi jadvallarni tekshirish va yaratish...")
        await conn.run_sync(Base.metadata.create_all)
        
        # 2. Mavjud jadvallarga yangi ustunlarni qo'shish
        try:
            print("cached_media jadvaliga yangi ustunlarni qo'shish (agar kerak bo'lsa)...")
            
            # Qo'shilayotgan ustunlar ro'yxati
            alters = [
                "ALTER TABLE cached_media ADD COLUMN IF NOT EXISTS file_id_audio VARCHAR(500);",
                "ALTER TABLE cached_media ADD COLUMN IF NOT EXISTS hit_count INTEGER DEFAULT 0;",
                "ALTER TABLE cached_media ADD COLUMN IF NOT EXISTS points_cost INTEGER DEFAULT 1;",
                "ALTER TABLE cached_media ADD COLUMN IF NOT EXISTS api_response_json TEXT;",
                "ALTER TABLE cached_media ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP;"
            ]
            
            for query in alters:
                try:
                    await conn.execute(text(query))
                except Exception as e:
                    print(f"Ustun qo'shishda xatolik (bu normal bo'lishi mumkin, agar u allaqachon mavjud bo'lsa): {e}")
                    
            print("✅ cached_media jadvali yangilandi!")
            
        except Exception as e:
            print(f"❌ Xatolik yuz berdi: {e}")

    print("🎉 Migratsiya muvaffaqiyatli yakunlandi!")

if __name__ == "__main__":
    asyncio.run(migrate_database())
