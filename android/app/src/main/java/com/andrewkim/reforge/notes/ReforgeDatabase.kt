package com.andrewkim.reforge.notes

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.TypeConverter
import androidx.room.TypeConverters
import java.time.Instant

class InstantConverters {
    @TypeConverter fun fromEpochMillis(value: Long?): Instant? = value?.let(Instant::ofEpochMilli)
    @TypeConverter fun toEpochMillis(value: Instant?): Long? = value?.toEpochMilli()
}

@Database(entities = [ContentNoteEntity::class], version = 1, exportSchema = true)
@TypeConverters(InstantConverters::class)
abstract class ReforgeDatabase : RoomDatabase() {
    abstract fun contentNoteDao(): ContentNoteDao

    companion object {
        const val NAME = "reforge.db"

        fun open(context: Context): ReforgeDatabase = Room.databaseBuilder(
            context.applicationContext, ReforgeDatabase::class.java, NAME,
        ).build()
    }
}
