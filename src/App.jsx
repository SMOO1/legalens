import React from 'react';
import Layout from './components/Layout';
import Uploader from './components/Uploader';

function App() {
  return (
    <Layout>
      <div className="h-full flex flex-col justify-center items-center py-10 md:py-20">
        <Uploader />

        {/* Features/Trust Section */}
        <div className="mt-24 grid grid-cols-1 md:grid-cols-3 gap-8 w-full max-w-5xl opacity-80">
          <div className="flex flex-col items-center text-center p-6 bg-white/40 rounded-2xl border border-white/60">
            <div className="w-12 h-12 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 mb-4">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
              </svg>
            </div>
            <h3 className="font-semibold text-gray-900 mb-2">Instant Analysis</h3>
            <p className="text-sm text-gray-600">Our machine learning models analyze dense legalese in seconds, saving you hours of manual review.</p>
          </div>

          <div className="flex flex-col items-center text-center p-6 bg-white/40 rounded-2xl border border-white/60">
            <div className="w-12 h-12 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 mb-4">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <h3 className="font-semibold text-gray-900 mb-2">Identify Red Flags</h3>
            <p className="text-sm text-gray-600">We catch unbalanced liability clauses, unreasonable termination terms, and hidden arbitration requirements.</p>
          </div>

          <div className="flex flex-col items-center text-center p-6 bg-white/40 rounded-2xl border border-white/60">
            <div className="w-12 h-12 rounded-full bg-teal-100 flex items-center justify-center text-teal-600 mb-4">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
              </svg>
            </div>
            <h3 className="font-semibold text-gray-900 mb-2">Total Privacy</h3>
            <p className="text-sm text-gray-600">Your documents never leave your browser for initial checks, and are securely deleted immediately following processing.</p>
          </div>
        </div>
      </div>
    </Layout>
  );
}

export default App;
