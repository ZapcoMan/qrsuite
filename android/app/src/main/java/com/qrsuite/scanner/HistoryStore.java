package com.qrsuite.scanner;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;

import java.util.ArrayList;
import java.util.List;

/** 识别历史：轻量 SQLite，只留最近 200 条，自动裁剪 */
public class HistoryStore extends SQLiteOpenHelper {

    private static final String DB = "qrsuite.db";
    private static final int VERSION = 1;
    private static final int MAX_ROWS = 200;
    private static final String TABLE = "history";

    public HistoryStore(Context ctx) {
        super(ctx, DB, null, VERSION);
    }

    @Override
    public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE " + TABLE + " ("
                + "_id INTEGER PRIMARY KEY AUTOINCREMENT,"
                + "ts INTEGER NOT NULL,"
                + "content TEXT NOT NULL,"
                + "format TEXT NOT NULL,"
                + "source TEXT NOT NULL)");
        db.execSQL("CREATE INDEX idx_ts ON " + TABLE + "(ts DESC)");
    }

    @Override
    public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
        db.execSQL("DROP TABLE IF EXISTS " + TABLE);
        onCreate(db);
    }

    /** 同一内容重复扫到只更新时间，避免刷屏 */
    public void add(String content, String format, String source) {
        if (content == null || content.isEmpty()) return;
        SQLiteDatabase db = getWritableDatabase();
        long now = System.currentTimeMillis();
        Cursor c = db.query(TABLE, new String[]{"_id"}, "content=?",
                new String[]{content}, null, null, null, "1");
        try {
            if (c.moveToFirst()) {
                ContentValues v = new ContentValues();
                v.put("ts", now);
                v.put("format", format);
                v.put("source", source);
                db.update(TABLE, v, "_id=?", new String[]{String.valueOf(c.getLong(0))});
            } else {
                ContentValues v = new ContentValues();
                v.put("ts", now);
                v.put("content", content);
                v.put("format", format);
                v.put("source", source);
                db.insert(TABLE, null, v);
            }
        } finally {
            c.close();
        }
        db.execSQL("DELETE FROM " + TABLE + " WHERE _id NOT IN "
                + "(SELECT _id FROM " + TABLE + " ORDER BY ts DESC LIMIT " + MAX_ROWS + ")");
    }

    public static class Entry {
        public final long id;
        public final long ts;
        public final String content;
        public final String format;
        public final String source;

        Entry(long id, long ts, String content, String format, String source) {
            this.id = id;
            this.ts = ts;
            this.content = content;
            this.format = format;
            this.source = source;
        }
    }

    public List<Entry> recent(int limit) {
        List<Entry> out = new ArrayList<>();
        Cursor c = getReadableDatabase().query(TABLE,
                new String[]{"_id", "ts", "content", "format", "source"},
                null, null, null, null, "ts DESC", String.valueOf(limit));
        try {
            while (c.moveToNext()) {
                out.add(new Entry(c.getLong(0), c.getLong(1), c.getString(2),
                        c.getString(3), c.getString(4)));
            }
        } finally {
            c.close();
        }
        return out;
    }

    public int count() {
        Cursor c = getReadableDatabase().rawQuery("SELECT COUNT(*) FROM " + TABLE, null);
        try {
            return c.moveToFirst() ? c.getInt(0) : 0;
        } finally {
            c.close();
        }
    }

    public void delete(long id) {
        getWritableDatabase().delete(TABLE, "_id=?", new String[]{String.valueOf(id)});
    }

    public void clear() {
        getWritableDatabase().delete(TABLE, null, null);
    }
}
