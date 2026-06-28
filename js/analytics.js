function calculateStudyStreak(sessions = []) {
  const daySet = new Set(
    sessions
      .map((session) => session.date && new Date(session.date))
      .filter((date) => date instanceof Date && !Number.isNaN(date.valueOf()))
      .map((date) => date.toISOString().slice(0, 10))
  );

  let streak = 0;
  const cursor = new Date();
  while (daySet.has(cursor.toISOString().slice(0, 10))) {
    streak += 1;
    cursor.setDate(cursor.getDate() - 1);
  }

  return streak;
}

export function calculateMetrics(bundle, courseState) {
  const questions = bundle.questions || [];
  const topics = bundle.meta.topics || Array.from(new Set(questions.map((q) => q.topic)));
  const answeredEntries = Object.entries(courseState.answered || {});
  const attempts = answeredEntries.reduce((sum, [, item]) => sum + (item.attempts || 0), 0);
  const correctAttempts = answeredEntries.reduce((sum, [, item]) => sum + (item.correct || 0), 0);
  const uniqueAnswered = answeredEntries.length;
  const missedCount = Object.keys(courseState.missed || {}).length;
  const bookmarkedCount = Object.keys(courseState.bookmarks || {}).length + Object.keys(courseState.reviewLater || {}).length;
  const accuracy = attempts ? Math.round((correctAttempts / attempts) * 100) : 0;

  const topicStats = topics.map((topic) => {
    const topicQuestions = questions.filter((question) => question.topic === topic);
    const stats = courseState.topicStats?.[topic] || { answered: 0, correct: 0, missed: 0 };
    const accuracyPct = stats.answered ? Math.round((stats.correct / stats.answered) * 100) : 0;
    const highProbability = topicQuestions.filter((question) => Number(question.probability || 0) >= 4).length;
    const bookmarks = topicQuestions.filter((question) => courseState.bookmarks?.[question.id] || courseState.reviewLater?.[question.id]).length;
    return {
      topic,
      total: topicQuestions.length,
      highProbability,
      answered: stats.answered,
      correct: stats.correct,
      missed: stats.missed,
      bookmarks,
      accuracy: accuracyPct
    };
  });

  const highProbabilityIds = new Set(questions.filter((question) => Number(question.probability || 0) >= 4).map((question) => question.id));
  const highProbabilityAnswers = answeredEntries.filter(([id]) => highProbabilityIds.has(id));
  const highProbabilityAttempts = highProbabilityAnswers.reduce((sum, [, item]) => sum + (item.attempts || 0), 0);
  const highProbabilityCorrect = highProbabilityAnswers.reduce((sum, [, item]) => sum + (item.correct || 0), 0);
  const highProbabilityAccuracy = highProbabilityAttempts ? Math.round((highProbabilityCorrect / highProbabilityAttempts) * 100) : accuracy;

  const mockHistory = courseState.mockExams || [];
  const mockAverage = mockHistory.length
    ? Math.round(mockHistory.reduce((sum, exam) => sum + (exam.scorePct || 0), 0) / mockHistory.length)
    : accuracy;

  const missedImprovement = uniqueAnswered
    ? Math.max(0, Math.round(100 - (missedCount / Math.max(uniqueAnswered, 1)) * 100))
    : 0;

  const readiness = Math.round(
    accuracy * 0.4 +
    highProbabilityAccuracy * 0.3 +
    mockAverage * 0.2 +
    missedImprovement * 0.1
  );

  const weakTopics = topicStats
    .filter((topic) => topic.total > 0)
    .sort((a, b) => {
      const aScore = (a.accuracy || 0) + Math.min(a.answered, 4);
      const bScore = (b.accuracy || 0) + Math.min(b.answered, 4);
      return aScore - bScore || b.highProbability - a.highProbability;
    })
    .slice(0, 5);

  const topicStatsWeakest = topicStats
    .filter((topic) => topic.total > 0)
    .slice()
    .sort((a, b) => a.accuracy - b.accuracy || b.missed - a.missed || b.highProbability - a.highProbability);

  const mostMissedTopics = topicStats
    .filter((topic) => topic.missed > 0)
    .slice()
    .sort((a, b) => b.missed - a.missed || a.accuracy - b.accuracy)
    .slice(0, 6);

  const highProbabilityTopics = topicStats
    .filter((topic) => topic.highProbability > 0)
    .sort((a, b) => b.highProbability - a.highProbability || a.accuracy - b.accuracy)
    .slice(0, 8);

  const recommendations = [];
  if (weakTopics[0]) {
    recommendations.push(`Review ${weakTopics[0].topic}`);
  }
  if (missedCount > 0) {
    recommendations.push("Review missed questions");
  }
  if (!mockHistory.length || mockAverage < 80) {
    recommendations.push("Take Mock OA");
  }
  weakTopics.slice(1, 3).forEach((topic) => {
    recommendations.push(`Drill ${topic.topic}`);
  });

  const recentQuestionId = (courseState.sessions || []).find((session) => session.questionId)?.questionId
    || answeredEntries
      .map(([id, item]) => ({ id, date: item.lastAnswered || "" }))
      .sort((a, b) => b.date.localeCompare(a.date))[0]?.id
    || "";

  return {
    totalQuestions: questions.length,
    attempts,
    uniqueAnswered,
    correctAttempts,
    missedCount,
    bookmarkedCount,
    accuracy,
    topicStats,
    topicStatsWeakest,
    highProbabilityAccuracy,
    highProbabilityTopics,
    mostMissedTopics,
    mockAverage,
    mockHistory,
    readiness,
    weakTopics,
    studyStreak: calculateStudyStreak(courseState.sessions || []),
    latestMock: mockHistory[0] || null,
    recentQuestionId,
    recommendations: Array.from(new Set(recommendations)).slice(0, 5)
  };
}

export function progressClass(value) {
  if (value >= 80) return "success";
  if (value >= 60) return "warning";
  return "danger";
}
