CREATE POLICY "Allow anon uploads to scans bucket"
ON storage.objects
FOR insert
TO anon
WITH CHECK (bucket_id='scans');