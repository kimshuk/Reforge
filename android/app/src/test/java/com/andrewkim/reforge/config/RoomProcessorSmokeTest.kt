package com.andrewkim.reforge.config

import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.PrimaryKey
import androidx.room.RoomDatabase
import org.junit.Assert.assertNotNull
import org.junit.Test

@Entity
internal data class ProcessorSmokeEntity(@PrimaryKey val id: Long)

@Dao
internal interface ProcessorSmokeDao

@Database(entities = [ProcessorSmokeEntity::class], version = 1, exportSchema = false)
internal abstract class ProcessorSmokeDatabase : RoomDatabase() {
    abstract fun dao(): ProcessorSmokeDao
}

class RoomProcessorSmokeTest {
    @Test fun generatesRoomImplementation() {
        assertNotNull(Class.forName("com.andrewkim.reforge.config.ProcessorSmokeDatabase_Impl"))
    }
}
