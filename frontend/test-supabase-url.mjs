import { createClient } from '@supabase/supabase-js';

const supabaseUrl = 'https://wtylhpjjxfjzpgopujok.supabase.co/rest/v1/';
const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind0eWxocGpqeGZqenBnb3B1am9rIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzgxNzg2OTQsImV4cCI6MjA5Mzc1NDY5NH0.scgF5eREljYsj8i5oVBkUTuDAMj_eOMw9-OB1oiKY-4';

// Monkey patch global fetch to see the exact URL requested
const originalFetch = global.fetch;
global.fetch = async (url, options) => {
  console.log(`[Intercepted Request] Method: ${options?.method || 'GET'} | URL: ${url}`);
  try {
    return await originalFetch(url, options);
  } catch (e) {
    console.log(`[Request Error] ${e.message}`);
    throw e;
  }
};

const supabase = createClient(supabaseUrl, supabaseKey);

async function run() {
  console.log('--- Testing Sign Up ---');
  const { error } = await supabase.auth.signUp({ email: 'test@example.com', password: 'password123' });
  if (error) console.log('Response Error:', error.message);
  
  console.log('\n--- Testing Guest Mode ---');
  const { error: guestError } = await supabase.auth.signInAnonymously();
  if (guestError) console.log('Response Error:', guestError.message);
}

run();
