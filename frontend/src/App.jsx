import React, { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { DashboardPage } from './pages/DashboardPage';
import { JobsPage } from './pages/JobsPage';
import { ApplicationsPage } from './pages/ApplicationsPage';
import { AutomationPage } from './pages/AutomationPage';
import { ProfilePage } from './pages/ProfilePage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { LoginPage } from './pages/LoginPage';

function MainApp() {
  const { user, loading } = useAuth();
  const [currentTab, setCurrentTab] = useState('dashboard');
  const [activeJobIdForPreparation, setActiveJobIdForPreparation] = useState(null);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0B0F19] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 border-3 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
          <p className="text-xs text-slate-400 font-medium">Initializing AI Career Co-Pilot...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return <LoginPage />;
  }

  const handlePrepareJob = (jobId) => {
    setActiveJobIdForPreparation(jobId);
    setCurrentTab('applications');
  };

  return (
    <div className="min-h-screen bg-[#0B0F19] flex text-slate-100 antialiased">
      {/* Sidebar Navigation */}
      <Sidebar
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        pendingApprovalsCount={0}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <Header onRefreshNeeded={() => {}} />

        <main className="flex-1 overflow-y-auto">
          {currentTab === 'dashboard' && (
            <DashboardPage
              onNavigateToTab={setCurrentTab}
              onPrepareJob={handlePrepareJob}
            />
          )}

          {currentTab === 'jobs' && (
            <JobsPage onPrepareApplication={handlePrepareJob} />
          )}

          {currentTab === 'applications' && (
            <ApplicationsPage
              activeJobIdForPreparation={activeJobIdForPreparation}
              onClearActiveJob={() => setActiveJobIdForPreparation(null)}
            />
          )}

          {currentTab === 'automation' && <AutomationPage />}

          {currentTab === 'profile' && <ProfilePage />}

          {currentTab === 'analytics' && <AnalyticsPage />}
        </main>
      </div>
    </div>
  );
}

export function App() {
  return (
    <AuthProvider>
      <MainApp />
    </AuthProvider>
  );
}
export default App;
